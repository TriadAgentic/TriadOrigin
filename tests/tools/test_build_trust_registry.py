"""Accept/reject battery for tools/build_trust_registry.py + wire-grammar differentials."""

from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import time
from typing import Any

TOOL_NAME = "build_trust_registry.py"
NOW_US = int(time.time() * 1_000_000)


def _write_spec(tmp_path: pathlib.Path, spec: Any) -> pathlib.Path:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def _build(run_tool, tmp_path: pathlib.Path, spec: Any):
    spec_path = _write_spec(tmp_path, spec)
    out_path = tmp_path / "registry.json"
    proc = run_tool(TOOL_NAME, "--spec", str(spec_path), "--out", str(out_path))
    return proc, out_path


class TestAccept:
    def test_valid_spec_builds_the_registry_shape(
            self, run_tool, tmp_path: pathlib.Path, registry_spec_factory) -> None:
        proc, out_path = _build(run_tool, tmp_path, registry_spec_factory(NOW_US))
        assert proc.returncode == 0, proc.stderr
        registry = json.loads(out_path.read_text(encoding="utf-8"))
        assert registry["schema"] == "triad.receipt_trust_registry.v1"
        assert len(registry["keys"]) == 2
        for row in registry["keys"]:
            assert row["algorithm"] == "Ed25519"
            assert row["status"] == "ACTIVE"
            assert len(base64.b64decode(row["public_key_base64"], validate=True)) == 32
        assert proc.stdout.strip() == hashlib.sha256(out_path.read_bytes()).hexdigest()

    def test_output_bytes_deterministic(
            self, run_tool, tmp_path: pathlib.Path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        one = tmp_path / "one"
        two = tmp_path / "two"
        one.mkdir()
        two.mkdir()
        proc_one, out_one = _build(run_tool, one, spec)
        proc_two, out_two = _build(run_tool, two, spec)
        assert proc_one.returncode == 0 and proc_two.returncode == 0
        assert out_one.read_bytes() == out_two.read_bytes()

    def test_registry_shape_matches_the_runner_fixture_law(
            self, run_tool, tmp_path: pathlib.Path, registry_spec_factory, frozen_runner) -> None:
        """The runner's own fixture registry rows and ours carry the same closed key surface."""
        proc, out_path = _build(run_tool, tmp_path, registry_spec_factory(NOW_US))
        assert proc.returncode == 0, proc.stderr
        registry = frozen_runner.strict_json_loads(out_path.read_text(encoding="utf-8"))
        assert registry["schema"] == "triad.receipt_trust_registry.v1"
        expected_row_keys = {
            "key_id", "identity", "role", "algorithm", "status", "public_key_base64",
            "valid_from_us", "valid_until_us", "approved_milestones",
        }
        for row in registry["keys"]:
            assert set(row) == expected_row_keys
            assert frozen_runner.parse_canonical_int64(row["valid_from_us"]) is not None
            assert frozen_runner.parse_canonical_int64(row["valid_until_us"]) is not None
            assert frozen_runner.strict_base64(row["public_key_base64"], 32) is not None


class TestReject:
    def _expect_refusal(self, run_tool, tmp_path: pathlib.Path, spec: Any, token: str) -> None:
        proc, out_path = _build(run_tool, tmp_path, spec)
        assert proc.returncode == 2, f"expected refusal {token}; stdout={proc.stdout}"
        assert token in proc.stderr, proc.stderr
        assert not out_path.exists()

    def test_duplicate_key_id(self, run_tool, tmp_path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        spec[1]["key_id"] = spec[0]["key_id"]
        self._expect_refusal(run_tool, tmp_path, spec, "DUPLICATE_KEY_ID")

    def test_bad_base64(self, run_tool, tmp_path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        spec[0]["public_key_base64"] = "!!!not-base64!!!"
        self._expect_refusal(run_tool, tmp_path, spec, "BAD_PUBLIC_KEY")

    def test_31_byte_key(self, run_tool, tmp_path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        spec[0]["public_key_base64"] = base64.b64encode(bytes(31)).decode("ascii")
        self._expect_refusal(run_tool, tmp_path, spec, "BAD_PUBLIC_KEY")

    def test_64_byte_blob_refused(self, run_tool, tmp_path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        spec[0]["public_key_base64"] = base64.b64encode(bytes(64)).decode("ascii")
        self._expect_refusal(run_tool, tmp_path, spec, "BAD_PUBLIC_KEY")

    def test_private_material_field_name_is_a_hard_error(
            self, run_tool, tmp_path, registry_spec_factory) -> None:
        for name in ("seed_b64", "private_key_base64", "secret", "signing_seed"):
            spec = registry_spec_factory(NOW_US)
            spec[0][name] = "AAAA"
            self._expect_refusal(run_tool, tmp_path, spec, "PRIVATE_MATERIAL_FIELD")

    def test_bad_int64_grammar(self, run_tool, tmp_path, registry_spec_factory) -> None:
        for bad in ("+5", "01", "-0", "1.0", "", " 1", str(2**63), 5):
            spec = registry_spec_factory(NOW_US)
            spec[0]["valid_from_us"] = bad
            self._expect_refusal(run_tool, tmp_path, spec, "BAD_INT64")

    def test_empty_validity_window(self, run_tool, tmp_path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        spec[0]["valid_until_us"] = spec[0]["valid_from_us"]
        self._expect_refusal(run_tool, tmp_path, spec, "EMPTY_VALIDITY_WINDOW")

    def test_bad_role(self, run_tool, tmp_path, registry_spec_factory) -> None:
        for bad_role in ("producer", "SIGNER", "", None):
            spec = registry_spec_factory(NOW_US)
            spec[0]["role"] = bad_role
            self._expect_refusal(run_tool, tmp_path, spec, "BAD_ROLE")

    def test_auditor_role_is_accepted(self, run_tool, tmp_path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        spec[0]["role"] = "AUDITOR"
        proc, out_path = _build(run_tool, tmp_path, spec)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(out_path.read_text())["keys"][0]["role"] == "AUDITOR"

    def test_bad_approved_milestones(self, run_tool, tmp_path, registry_spec_factory) -> None:
        for bad in ([], ["B11"], ["ALL", "B05"], ["B05", "B05"], "SOME", [5]):
            spec = registry_spec_factory(NOW_US)
            spec[0]["approved_milestones"] = bad
            self._expect_refusal(run_tool, tmp_path, spec, "BAD_APPROVED_MILESTONES")

    def test_explicit_milestone_list_is_accepted(
            self, run_tool, tmp_path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        spec[0]["approved_milestones"] = ["B01", "B05", "B10"]
        proc, _ = _build(run_tool, tmp_path, spec)
        assert proc.returncode == 0, proc.stderr

    def test_empty_spec_refused(self, run_tool, tmp_path) -> None:
        self._expect_refusal(run_tool, tmp_path, [], "EMPTY_SPEC")

    def test_non_array_root_refused(self, run_tool, tmp_path) -> None:
        self._expect_refusal(run_tool, tmp_path, {"keys": []}, "BAD_SPEC_ROOT")

    def test_unknown_row_key_refused(self, run_tool, tmp_path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        spec[0]["note"] = "hello"
        self._expect_refusal(run_tool, tmp_path, spec, "UNKNOWN_ROW_KEY")

    def test_wrong_forced_algorithm_refused(
            self, run_tool, tmp_path, registry_spec_factory) -> None:
        spec = registry_spec_factory(NOW_US)
        spec[0]["algorithm"] = "RSA"
        self._expect_refusal(run_tool, tmp_path, spec, "BAD_ALGORITHM")

    def test_out_inside_repo_refused(
            self, run_tool, tmp_path, registry_spec_factory, repo_root) -> None:
        spec_path = _write_spec(tmp_path, registry_spec_factory(NOW_US))
        target = repo_root / "tmp_registry_should_never_exist.json"
        proc = run_tool(TOOL_NAME, "--spec", str(spec_path), "--out", str(target))
        assert proc.returncode == 2
        assert "OUT_PATH_INSIDE_REPOSITORY" in proc.stderr
        assert not target.exists()


class TestInt64GrammarDifferential:
    BATTERY: tuple[Any, ...] = (
        "0", "1", "-1", "42", "-42", "01", "+5", "-0", "1.0", "", " 1", "1 ", "1e3",
        str(2**63 - 1), str(2**63), str(-(2**63)), str(-(2**63) - 1),
        5, None, True, False, "٥", "0x10",
    )

    def test_tool_grammar_matches_runner_exactly(self, tool_registry, frozen_runner) -> None:
        for value in self.BATTERY:
            assert tool_registry.parse_canonical_int64(value) == \
                frozen_runner.parse_canonical_int64(value), f"int64 grammar diverged on {value!r}"

    def test_receipt_tool_grammar_matches_runner_exactly(
            self, tool_receipt, frozen_runner) -> None:
        for value in self.BATTERY:
            assert tool_receipt.parse_canonical_int64(value) == \
                frozen_runner.parse_canonical_int64(value), f"int64 grammar diverged on {value!r}"
