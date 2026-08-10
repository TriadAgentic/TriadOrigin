"""Differential tests: tools/ed25519_verify.py vs the frozen audit runner.

The frozen runner ``audit_package/triad_origin_b01_b10_audit.py`` (v1.2.0) is the single source
of truth for every constant and verdict.  These tests load BOTH modules from their file paths and
assert byte-/verdict-equality.  The runner's ``_ed25519_sign_for_self_test`` is used here — and
only here, with throwaway in-test seeds assembled at runtime — to generate valid signatures; the
shipped tool contains no signing code.

The repository at /home/user/TriadOrigin is READ-ONLY: ``sys.dont_write_bytecode`` is set before
the runner module is executed so no ``__pycache__`` is ever written next to it.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
from types import ModuleType
from typing import Any

import pytest

sys.dont_write_bytecode = True  # MUST precede loading the runner from the read-only repo.

# Paths resolved relative to this test file so the differential runs from any checkout.
REPO = pathlib.Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO / "audit_package" / "triad_origin_b01_b10_audit.py"
TOOL_PATH = REPO / "tools" / "ed25519_verify.py"

# Sibling-or-skip: the frozen runner is untracked (audit_package/ gitignored), absent in a fresh
# clone and present only when the operator deploys it beside the repo. Skip the whole differential
# module cleanly before any module-level runner read when it is not present.
if not RUNNER_PATH.is_file():
    pytest.skip(
        "frozen audit runner absent (audit_package/ untracked); ed25519 differential runs only "
        "when the runner is deployed beside the repo",
        allow_module_level=True,
    )

# The frozen pin (assembled from chunks so no 64-hex literal appears in tracked source).
RUNNER_SHA256 = "".join(
    ("12c8896479b90216", "5fa2c6d3e7565ea8", "402b49fcfe2d044f", "6fd69153926d35a2"))

# RFC 8032 test vector 1 (public data — the runner's own self-test vector at ~L4292).
RFC8032_PUBLIC_KEY = bytes.fromhex("".join(
    ("d75a980182b10ab7", "d54bfed3c964073a", "0ee172f3daa62325", "af021a68f707511a")))
RFC8032_SIGNATURE = bytes.fromhex("".join(
    ("e5564300c360ac72", "9086e2cc806e828a", "84877f1eb8e5d974", "d873e06522490155",
     "5fb8821590a33bac", "c61e39701cf9b46b", "d25bf5f0595bbe24", "655141438e7a100b")))


def _load_module(name: str, path: pathlib.Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_runner() -> ModuleType:
    data = RUNNER_PATH.read_bytes()
    assert hashlib.sha256(data).hexdigest() == RUNNER_SHA256, (
        "frozen runner bytes do not match the pinned SHA-256; refuse the differential")
    # Importing must not execute main: the runner must carry a __main__ guard.
    assert b'if __name__ == "__main__":' in data
    assert sys.dont_write_bytecode is True
    return _load_module("triad_origin_b01_b10_audit_frozen", RUNNER_PATH)


RUNNER = _load_runner()
TOOL = _load_module("ed25519_verify_staged", TOOL_PATH)


def _throwaway_seed(tag: bytes) -> bytes:
    # Assembled at runtime; never a credential-shaped literal in source.
    return hashlib.sha256(b"b0r-throwaway-fixture-" + tag).digest()


def _keypair(tag: bytes, message: bytes) -> tuple[bytes, bytes]:
    return RUNNER._ed25519_sign_for_self_test(_throwaway_seed(tag), message)


def _differential_cases() -> list[tuple[str, bytes, bytes, bytes, bool | None]]:
    """(label, public_key, message, signature, expected) — expected None = differential only."""
    cases: list[tuple[str, bytes, bytes, bytes, bool | None]] = []

    # Valid signatures over various messages.
    messages = [b"", b"a", b"strict Ed25519 negative fixture", b"x" * 4096,
                "unicode-ω世界".encode("utf-8")]
    for index, message in enumerate(messages):
        public_key, signature = _keypair(str(index).encode("ascii"), message)
        cases.append((f"valid-{index}", public_key, message, signature, True))

    flip_message = b"flip message"
    public_key, signature = _keypair(b"flip", flip_message)

    # Bit-flipped signatures (R half and s half, both ends).
    for position in (0, 31, 32, 63):
        flipped = bytearray(signature)
        flipped[position] ^= 0x01
        cases.append((f"sig-bitflip-{position}", public_key, flip_message, bytes(flipped), False))

    # Message tampering.
    cases.append(("msg-tampered", public_key, b"flip messagE", signature, False))
    cases.append(("msg-extended", public_key, flip_message + b"\x00", signature, False))

    # Wrong keys.
    other_key, other_signature = _keypair(b"other", flip_message)
    cases.append(("wrong-key", other_key, flip_message, signature, False))
    cases.append(("swapped-signature", public_key, flip_message, other_signature, False))

    # Truncated / wrong-length inputs.
    cases.append(("pk-31-bytes", public_key[:31], flip_message, signature, False))
    cases.append(("pk-33-bytes", public_key + b"\x00", flip_message, signature, False))
    cases.append(("pk-empty", b"", flip_message, signature, False))
    cases.append(("sig-63-bytes", public_key, flip_message, signature[:63], False))
    cases.append(("sig-65-bytes", public_key, flip_message, signature + b"\x00", False))
    cases.append(("sig-empty", public_key, flip_message, b"", False))

    # All-zero public key.
    cases.append(("all-zero-key", b"\x00" * 32, flip_message, signature, False))

    # Scalar bound: s >= L rejected.
    ell = RUNNER._ED_L
    cases.append(("scalar-eq-L", public_key, flip_message,
                  signature[:32] + ell.to_bytes(32, "little"), False))
    s_value = int.from_bytes(signature[32:], "little")
    cases.append(("scalar-plus-L", public_key, flip_message,
                  signature[:32] + (s_value + ell).to_bytes(32, "little"), False))

    # Non-canonical y >= q encodings.
    q_bytes = (2**255 - 19).to_bytes(32, "little")
    cases.append(("r-y-ge-q", public_key, flip_message, q_bytes + signature[32:], False))
    cases.append(("pk-y-ge-q", q_bytes, flip_message, signature, False))

    # Small-order / non-canonical identity vectors — the exact construction of the runner's
    # own self-test "Ed25519 rejects small-order and noncanonical identity encodings" (~L4303).
    message = b"strict Ed25519 negative fixture"
    seed = bytes(range(32))
    expanded = hashlib.sha512(seed).digest()
    scalar_bytes = bytearray(expanded[:32])
    scalar_bytes[0] &= 248
    scalar_bytes[31] &= 63
    scalar_bytes[31] |= 64
    secret_scalar = int.from_bytes(scalar_bytes, "little")
    strict_pk = RUNNER._ed_encode(RUNNER._ed_scalar_mult(RUNNER._ED_B, secret_scalar))
    identity = (1).to_bytes(32, "little")
    noncanonical_identity = (1 | (1 << 255)).to_bytes(32, "little")
    challenge = int.from_bytes(
        hashlib.sha512(identity + strict_pk + message).digest(), "little") % ell
    forged_scalar = (challenge * secret_scalar) % ell
    forged_scalar_bytes = forged_scalar.to_bytes(32, "little")
    cases.append(("small-order-identity-R", strict_pk, message,
                  identity + forged_scalar_bytes, False))
    cases.append(("noncanonical-identity-R", strict_pk, message,
                  noncanonical_identity + forged_scalar_bytes, False))
    cases.append(("identity-public-key", identity, message, identity + b"\x00" * 32, False))

    # Further low-order encodings: the order-2 point (y = -1) and non-canonical zero.
    order_two = (2**255 - 20).to_bytes(32, "little")
    cases.append(("order2-R", strict_pk, message, order_two + forged_scalar_bytes, False))
    cases.append(("order2-pk", order_two, message, identity + forged_scalar_bytes, False))
    noncanonical_zero = (1 << 255).to_bytes(32, "little")
    cases.append(("noncanonical-zero-R", strict_pk, message,
                  noncanonical_zero + forged_scalar_bytes, False))
    cases.append(("zero-y-R", strict_pk, message,
                  (0).to_bytes(32, "little") + forged_scalar_bytes, False))

    # RFC 8032 vector 1 (the runner's own vector) and its tamper case.
    cases.append(("rfc8032-vector", RFC8032_PUBLIC_KEY, b"", RFC8032_SIGNATURE, True))
    cases.append(("rfc8032-tampered", RFC8032_PUBLIC_KEY, b"tampered", RFC8032_SIGNATURE, False))
    return cases


def test_runner_identity_guard_and_frozen_pin() -> None:
    assert RUNNER_PATH.is_file()
    assert callable(getattr(RUNNER, "main"))
    # Importing did not execute main (a SystemExit at import would have failed collection).
    assert getattr(RUNNER, "ed25519_verify") is not TOOL.ed25519_verify


def test_differential_ed25519_verify_matches_runner_on_every_case() -> None:
    cases = _differential_cases()
    assert len(cases) >= 20
    labels = [label for label, *_ in cases]
    assert len(labels) == len(set(labels))
    for label, public_key, message, signature, expected in cases:
        tool_verdict = TOOL.ed25519_verify(public_key, message, signature)
        runner_verdict = RUNNER.ed25519_verify(public_key, message, signature)
        assert isinstance(tool_verdict, bool), label
        assert tool_verdict == runner_verdict, f"differential mismatch: {label}"
        if expected is not None:
            assert tool_verdict is expected, f"absolute verdict mismatch: {label}"


def test_pae_differential_and_exact_bytes() -> None:
    vectors: list[tuple[str, bytes]] = [
        ("", b""),
        ("t", b"p"),
        ("application/vnd.in-toto+json", b"{}"),
        ("тип/данные", "payload-ω".encode("utf-8")),
        ("x" * 300, bytes(range(256)) * 8),
        ("application/vnd.triad.receipt.v3+json", b'{"a":1}'),
    ]
    for payload_type, payload in vectors:
        assert TOOL.pae(payload_type, payload) == RUNNER.dsse_pae(payload_type, payload), payload_type
    # Exact DSSEv1 byte format.
    assert TOOL.pae("t", b"p") == b"DSSEv1 1 t 1 p"
    assert TOOL.pae("", b"") == b"DSSEv1 0  0 "


def test_strict_base64_differential() -> None:
    samples: list[Any] = ["QQ==", "QQ", "Q Q==", "QQ=", "####", "", 5, None, b"QQ==", "QQ==\n"]
    for sample in samples:
        for expected_length in (None, 1, 32):
            assert TOOL.strict_base64(sample, expected_length) == RUNNER.strict_base64(
                sample, expected_length), (sample, expected_length)


# ---------------------------------------------------------------------------- CLI fixtures ----

PAYLOAD_TYPE = "application/vnd.triad.test+json"


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


def _registry_row(key_id: str, identity: str, public_key: bytes,
                  algorithm: str, status: str) -> dict[str, Any]:
    return {
        "key_id": key_id, "identity": identity, "role": "PRODUCER",
        "algorithm": algorithm, "status": status,
        "public_key_base64": _b64(public_key),
        "approved_milestones": ["ALL"],
    }


def _build_fixture(tmp_path: pathlib.Path) -> dict[str, Any]:
    payload_bytes = json.dumps(
        {"schema": "triad.test.v1", "value": 1}, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    pae_bytes = RUNNER.dsse_pae(PAYLOAD_TYPE, payload_bytes)

    producer_public, producer_sig = RUNNER._ed25519_sign_for_self_test(
        _throwaway_seed(b"producer"), pae_bytes)
    counter_public, counter_sig = RUNNER._ed25519_sign_for_self_test(
        _throwaway_seed(b"countersigner"), pae_bytes)
    badsig_public, _ = RUNNER._ed25519_sign_for_self_test(_throwaway_seed(b"badsig"), pae_bytes)
    revoked_public, revoked_sig = RUNNER._ed25519_sign_for_self_test(
        _throwaway_seed(b"revoked"), pae_bytes)
    rsa_public, rsa_sig = RUNNER._ed25519_sign_for_self_test(_throwaway_seed(b"rsa"), pae_bytes)

    registry = {
        "schema": "triad.receipt_trust_registry.v1",
        "keys": [
            _registry_row("k-producer", "builder-a", producer_public, "Ed25519", "ACTIVE"),
            _registry_row("k-counter", "reviewer-b", counter_public, "Ed25519", "ACTIVE"),
            _registry_row("k-badsig", "builder-c", badsig_public, "Ed25519", "ACTIVE"),
            _registry_row("k-revoked", "old-d", revoked_public, "Ed25519", "REVOKED"),
            _registry_row("k-rsa", "wrong-e", rsa_public, "RSA", "ACTIVE"),
        ],
    }
    envelope = {
        "payloadType": PAYLOAD_TYPE,
        "payload": _b64(payload_bytes),
        "signatures": [
            {"keyid": "k-producer", "sig": _b64(producer_sig)},
            {"keyid": "k-counter", "sig": _b64(counter_sig)},
            # Valid ACTIVE Ed25519 key, but the signature bytes belong to another key.
            {"keyid": "k-badsig", "sig": _b64(producer_sig)},
            {"keyid": "k-revoked", "sig": _b64(revoked_sig)},
            {"keyid": "k-rsa", "sig": _b64(rsa_sig)},
            {"keyid": "k-unknown", "sig": _b64(producer_sig)},
        ],
    }
    envelope_path = tmp_path / "envelope.json"
    registry_path = tmp_path / "registry.json"
    envelope_path.write_text(json.dumps(envelope, sort_keys=True), encoding="utf-8")
    registry_path.write_text(json.dumps(registry, sort_keys=True), encoding="utf-8")
    return {
        "envelope": envelope, "registry": registry, "payload_bytes": payload_bytes,
        "envelope_path": envelope_path, "registry_path": registry_path,
    }


def _run_cli(*argv: str, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
    return subprocess.run(
        [sys.executable, *argv], text=True, capture_output=True, timeout=120, check=False,
        cwd=str(cwd) if cwd is not None else None, env=env)


def test_cli_happy_path_reports_per_signature_verdicts(tmp_path: pathlib.Path) -> None:
    fixture = _build_fixture(tmp_path)
    proc = _run_cli(str(TOOL_PATH), "--envelope", str(fixture["envelope_path"]),
                    "--registry", str(fixture["registry_path"]))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.endswith("\n") and proc.stdout.count("\n") == 1
    report = json.loads(proc.stdout)
    assert set(report) == {"verified_keyids", "failed_keyids", "failed_rows", "distinct_identities"}
    assert report["verified_keyids"] == ["k-producer", "k-counter"]
    assert report["failed_keyids"] == ["k-badsig", "k-revoked", "k-rsa", "k-unknown"]
    assert report["failed_rows"] == [2, 3, 4, 5]
    assert report["distinct_identities"] == 2


def test_cli_accepts_wrapped_dsse_event(tmp_path: pathlib.Path) -> None:
    fixture = _build_fixture(tmp_path)
    wrapped_path = tmp_path / "event.json"
    wrapped_path.write_text(
        json.dumps({"schema": "triad.event", "dsse": fixture["envelope"]}, sort_keys=True),
        encoding="utf-8")
    proc = _run_cli(str(TOOL_PATH), "--envelope", str(wrapped_path),
                    "--registry", str(fixture["registry_path"]))
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["verified_keyids"] == ["k-producer", "k-counter"]
    assert report["distinct_identities"] == 2


def test_cli_tampered_payload_fails_everything(tmp_path: pathlib.Path) -> None:
    fixture = _build_fixture(tmp_path)
    tampered = copy.deepcopy(fixture["envelope"])
    tampered["payload"] = _b64(fixture["payload_bytes"] + b" ")
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered, sort_keys=True), encoding="utf-8")
    proc = _run_cli(str(TOOL_PATH), "--envelope", str(tampered_path),
                    "--registry", str(fixture["registry_path"]))
    assert proc.returncode == 1
    report = json.loads(proc.stdout)
    assert report["verified_keyids"] == []
    assert report["distinct_identities"] == 0
    assert set(report["failed_keyids"]) == {
        "k-producer", "k-counter", "k-badsig", "k-revoked", "k-rsa", "k-unknown"}
    assert report["failed_rows"] == [0, 1, 2, 3, 4, 5]


def test_cli_payload_type_pin(tmp_path: pathlib.Path) -> None:
    fixture = _build_fixture(tmp_path)
    mismatch = _run_cli(str(TOOL_PATH), "--envelope", str(fixture["envelope_path"]),
                        "--registry", str(fixture["registry_path"]),
                        "--payload-type", "application/other")
    assert mismatch.returncode == 1
    assert json.loads(mismatch.stdout)["verified_keyids"] == []
    exact = _run_cli(str(TOOL_PATH), "--envelope", str(fixture["envelope_path"]),
                     "--registry", str(fixture["registry_path"]),
                     "--payload-type", PAYLOAD_TYPE)
    assert exact.returncode == 0
    assert json.loads(exact.stdout)["verified_keyids"] == ["k-producer", "k-counter"]


def test_cli_wrong_registry_schema_trusts_no_key(tmp_path: pathlib.Path) -> None:
    fixture = _build_fixture(tmp_path)
    bad_registry = dict(fixture["registry"], schema="triad.receipt_trust_registry.v2")
    bad_path = tmp_path / "bad_registry.json"
    bad_path.write_text(json.dumps(bad_registry, sort_keys=True), encoding="utf-8")
    proc = _run_cli(str(TOOL_PATH), "--envelope", str(fixture["envelope_path"]),
                    "--registry", str(bad_path))
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["verified_keyids"] == []
    assert "trusting no key" in proc.stderr


def test_cli_unreadable_input_is_a_usage_error(tmp_path: pathlib.Path) -> None:
    fixture = _build_fixture(tmp_path)
    proc = _run_cli(str(TOOL_PATH), "--envelope", str(tmp_path / "missing.json"),
                    "--registry", str(fixture["registry_path"]))
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.strip()
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text('{"payloadType": "a", "payloadType": "b"}', encoding="utf-8")
    dup = _run_cli(str(TOOL_PATH), "--envelope", str(duplicate_path),
                   "--registry", str(fixture["registry_path"]))
    assert dup.returncode == 2
    assert "duplicate" in dup.stderr


def test_tool_is_stdlib_only_and_verify_only() -> None:
    source = TOOL_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = {"__future__", "argparse", "base64", "binascii", "hashlib", "json", "sys", "typing"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module is not None and node.level == 0
            imported.add(node.module.split(".")[0])
    assert imported <= allowed, imported
    # STRICTLY NO SIGNING and no private-key handling: the runner's signing helper and the
    # signing-only point encoder must not exist in the shipped tool.
    assert "sign_for_self_test" not in source
    assert "_ed_encode" not in source
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert "sign" not in node.name.lower(), node.name
    lowered = source.lower()
    for banned in ("private_key", "secret_key", "urllib", "socket", "http.client", "ssl"):
        assert banned not in lowered, banned
    # The tool has a __main__ guard and importing it did not run main.
    assert 'if __name__ == "__main__":' in source
    assert callable(TOOL.main)


def test_tool_invocation_leaves_a_clean_tree(tmp_path: pathlib.Path) -> None:
    """Tree-mutation law simulation: run the tool as ``python tools/ed25519_verify.py`` inside a
    fresh clone-shaped tree and prove nothing — including __pycache__ — appears afterward."""
    clone = tmp_path / "clone"
    (clone / "tools").mkdir(parents=True)
    (clone / "tools" / "ed25519_verify.py").write_bytes(TOOL_PATH.read_bytes())
    outside = tmp_path / "fixtures"
    outside.mkdir()
    fixture = _build_fixture(outside)

    def snapshot() -> list[str]:
        return sorted(str(path.relative_to(clone)) for path in clone.rglob("*"))

    before = snapshot()
    proc = _run_cli("tools/ed25519_verify.py", "--envelope", str(fixture["envelope_path"]),
                    "--registry", str(fixture["registry_path"]), cwd=clone)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["verified_keyids"] == ["k-producer", "k-counter"]
    assert snapshot() == before
    assert not list(clone.rglob("__pycache__"))


def test_library_face_matches_cli_semantics(tmp_path: pathlib.Path) -> None:
    fixture = _build_fixture(tmp_path)
    report = TOOL.verify_envelope_against_registry(fixture["envelope"], fixture["registry"])
    assert report == {
        "verified_keyids": ["k-producer", "k-counter"],
        "failed_keyids": ["k-badsig", "k-revoked", "k-rsa", "k-unknown"],
        "failed_rows": [2, 3, 4, 5],
        "distinct_identities": 2,
    }
    pinned = TOOL.verify_envelope_against_registry(
        fixture["envelope"], fixture["registry"], PAYLOAD_TYPE)
    assert pinned == report
    assert TOOL.verify_envelope_against_registry(
        fixture["envelope"], fixture["registry"], "application/other",
    )["verified_keyids"] == []
    assert TOOL.verify_envelope_against_registry(None, fixture["registry"]) == {
        "verified_keyids": [], "failed_keyids": [], "failed_rows": [], "distinct_identities": 0}


# ------------------------------------------------ FINDING 1: duplicate-registry refusal ----


def test_cli_duplicate_registry_key_id_is_a_hard_error(tmp_path: pathlib.Path) -> None:
    """Duplicate key_id in the registry => exit nonzero, stderr names the id, empty stdout.

    Mirrors the runner's refusal (its registry validation appends
    "trust registry contains duplicate key IDs" whenever
    ``len(key_ids) != len(set(key_ids))`` over ``str(row.get("key_id"))`` for dict rows) —
    the CLI must never fall back to a last-wins map.
    """
    fixture = _build_fixture(tmp_path)
    registry = copy.deepcopy(fixture["registry"])
    duplicate_row = copy.deepcopy(registry["keys"][0])  # a second "k-producer" row
    duplicate_row["identity"] = "impostor-z"
    registry["keys"].append(duplicate_row)

    # The runner's own uniqueness expression flags this registry (refusal parity).
    runner_key_ids = [str(row.get("key_id")) for row in registry["keys"] if isinstance(row, dict)]
    assert len(runner_key_ids) != len(set(runner_key_ids))

    dup_path = tmp_path / "dup_registry.json"
    dup_path.write_text(json.dumps(registry, sort_keys=True), encoding="utf-8")
    proc = _run_cli(str(TOOL_PATH), "--envelope", str(fixture["envelope_path"]),
                    "--registry", str(dup_path))
    assert proc.returncode != 0
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "duplicate key ID" in proc.stderr
    assert "k-producer" in proc.stderr

    # Library face: the same refusal, as a ValueError naming the duplicate id.
    with pytest.raises(ValueError, match="k-producer"):
        TOOL.verify_envelope_against_registry(fixture["envelope"], registry)
    with pytest.raises(ValueError):
        TOOL._registry_keys(registry)


def test_duplicate_detection_uses_the_runners_str_coercion(tmp_path: pathlib.Path) -> None:
    """Two dict rows WITHOUT a key_id both coerce to str(None) == "None" — the runner's
    uniqueness expression counts that as a duplicate, so the tool must refuse it too;
    non-dict rows are skipped by both, exactly as the runner filters them."""
    registry: dict[str, Any] = {
        "schema": "triad.receipt_trust_registry.v1",
        "keys": [
            {"identity": "a"},  # no key_id -> "None"
            "not-a-dict",       # skipped by both sides
            {"identity": "b"},  # no key_id -> "None" again: duplicate
        ],
    }
    runner_key_ids = [str(row.get("key_id")) for row in registry["keys"] if isinstance(row, dict)]
    assert len(runner_key_ids) != len(set(runner_key_ids))
    with pytest.raises(ValueError, match="None"):
        TOOL._registry_keys(registry)
    # A unique registry (with a non-dict row) still loads, keyed by str(key_id).
    unique = {
        "schema": "triad.receipt_trust_registry.v1",
        "keys": [{"key_id": "k-a"}, "not-a-dict", {"key_id": "k-b"}],
    }
    assert set(TOOL._registry_keys(unique)) == {"k-a", "k-b"}


# ------------------------------------- FINDING 2: strict_json_loads non-finite parity ----


def test_strict_json_non_finite_parity_with_runner() -> None:
    """Differential: the tool's strict loader must refuse exactly what the runner's
    ``strict_json_loads`` refuses — the non-finite constants NaN / Infinity / -Infinity —
    and must accept the same finite documents."""
    rejected = ["NaN", "Infinity", "-Infinity", "[NaN]", "[Infinity]", "[-Infinity]",
                '{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}',
                '{"a": [1, {"b": -Infinity}]}']
    for sample in rejected:
        with pytest.raises(json.JSONDecodeError):
            RUNNER.strict_json_loads(sample)
        with pytest.raises(json.JSONDecodeError):
            TOOL._strict_json_loads(sample)
    accepted = ['{"a": 1.5}', "[1, 2.25, -3, 1e300]", '"NaN"', '"Infinity"',
                '{"nan": "Infinity", "x": null}']
    for sample in accepted:
        assert TOOL._strict_json_loads(sample) == RUNNER.strict_json_loads(sample), sample
    # Duplicate-key refusal stays paired with the runner's DuplicateJSONKey (a ValueError).
    for sample in ['{"a": 1, "a": 2}', '{"x": {"a": 1, "a": 2}}']:
        with pytest.raises(ValueError):
            RUNNER.strict_json_loads(sample)
        with pytest.raises(ValueError):
            TOOL._strict_json_loads(sample)


def test_cli_rejects_non_finite_json_inputs(tmp_path: pathlib.Path) -> None:
    fixture = _build_fixture(tmp_path)
    for token in ("NaN", "Infinity", "-Infinity"):
        bad_path = tmp_path / f"nonfinite_{token.strip('-')}_{len(token)}.json"
        bad_path.write_text('{"payloadType": "a", "x": ' + token + "}", encoding="utf-8")
        # Non-finite envelope: usage error, nothing on stdout.
        proc = _run_cli(str(TOOL_PATH), "--envelope", str(bad_path),
                        "--registry", str(fixture["registry_path"]))
        assert proc.returncode == 2, token
        assert proc.stdout == ""
        assert "non-finite" in proc.stderr
        # Non-finite registry: same refusal.
        proc = _run_cli(str(TOOL_PATH), "--envelope", str(fixture["envelope_path"]),
                        "--registry", str(bad_path))
        assert proc.returncode == 2, token
        assert proc.stdout == ""
        assert "non-finite" in proc.stderr


# ------------------------------ FINDING 3: duplicate-keyid signature-row determinism ----


def _dup_row_fixture(tmp_path: pathlib.Path) -> dict[str, Any]:
    payload_bytes = json.dumps(
        {"schema": "triad.test.v1", "value": 2}, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    pae_bytes = RUNNER.dsse_pae(PAYLOAD_TYPE, payload_bytes)
    public, good_sig = RUNNER._ed25519_sign_for_self_test(_throwaway_seed(b"dup-row"), pae_bytes)
    bad_sig = bytearray(good_sig)
    bad_sig[40] ^= 0x01  # decodes strictly to 64 bytes; fails Ed25519 verification
    registry = {
        "schema": "triad.receipt_trust_registry.v1",
        "keys": [_registry_row("k-dup", "dup-identity", public, "Ed25519", "ACTIVE")],
    }
    return {
        "registry": registry, "payload": _b64(payload_bytes),
        "good": {"keyid": "k-dup", "sig": _b64(good_sig)},
        "bad": {"keyid": "k-dup", "sig": _b64(bytes(bad_sig))},
    }


def test_same_keyid_verifying_and_failing_rows_never_lands_in_both_lists(
        tmp_path: pathlib.Path) -> None:
    fixture = _dup_row_fixture(tmp_path)
    # Both orderings: good-then-bad and bad-then-good.
    for rows, expected_failed_rows in (
        ([fixture["good"], fixture["bad"]], [1]),
        ([fixture["bad"], fixture["good"]], [0]),
    ):
        envelope = {"payloadType": PAYLOAD_TYPE, "payload": fixture["payload"],
                    "signatures": rows}
        report = TOOL.verify_envelope_against_registry(envelope, fixture["registry"])
        assert report["verified_keyids"] == ["k-dup"]
        assert report["failed_keyids"] == []  # NEVER in both lists
        assert report["failed_rows"] == expected_failed_rows
        assert report["distinct_identities"] == 1
        assert set(report["verified_keyids"]).isdisjoint(report["failed_keyids"])

    # All rows failing for the keyid: it lands in failed_keyids exactly once.
    envelope = {"payloadType": PAYLOAD_TYPE, "payload": fixture["payload"],
                "signatures": [fixture["bad"], fixture["bad"]]}
    report = TOOL.verify_envelope_against_registry(envelope, fixture["registry"])
    assert report == {
        "verified_keyids": [], "failed_keyids": ["k-dup"], "failed_rows": [0, 1],
        "distinct_identities": 0,
    }

    # Two verifying rows: keyid listed once, no failed rows.
    envelope = {"payloadType": PAYLOAD_TYPE, "payload": fixture["payload"],
                "signatures": [fixture["good"], fixture["good"]]}
    report = TOOL.verify_envelope_against_registry(envelope, fixture["registry"])
    assert report == {
        "verified_keyids": ["k-dup"], "failed_keyids": [], "failed_rows": [],
        "distinct_identities": 1,
    }


def test_cli_duplicate_keyid_rows_report_is_deterministic(tmp_path: pathlib.Path) -> None:
    fixture = _dup_row_fixture(tmp_path)
    envelope = {"payloadType": PAYLOAD_TYPE, "payload": fixture["payload"],
                "signatures": [fixture["bad"], fixture["good"]]}
    envelope_path = tmp_path / "dup_rows_envelope.json"
    registry_path = tmp_path / "dup_rows_registry.json"
    envelope_path.write_text(json.dumps(envelope, sort_keys=True), encoding="utf-8")
    registry_path.write_text(json.dumps(fixture["registry"], sort_keys=True), encoding="utf-8")
    proc = _run_cli(str(TOOL_PATH), "--envelope", str(envelope_path),
                    "--registry", str(registry_path))
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report == {
        "distinct_identities": 1, "failed_keyids": [], "failed_rows": [0],
        "verified_keyids": ["k-dup"],
    }
    # Byte-determinism of the CLI face across two runs.
    again = _run_cli(str(TOOL_PATH), "--envelope", str(envelope_path),
                     "--registry", str(registry_path))
    assert again.stdout == proc.stdout and again.returncode == proc.returncode
