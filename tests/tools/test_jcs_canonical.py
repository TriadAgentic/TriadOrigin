"""Differential tests: tools/jcs_canonical.py vs the frozen audit runner.

The frozen runner ``/home/user/TriadOrigin/audit_package/triad_origin_b01_b10_audit.py``
(v1.2.0) is the single source of truth.  Its ``jcs_canonical_bytes`` (L417-457) and
``strict_json_loads`` (L404-414) are loaded via importlib and every behavior of the
staged tool is asserted byte-for-byte / message-for-message against it.

The repo is READ-ONLY: ``sys.dont_write_bytecode`` is set before the runner module is
executed so no ``__pycache__`` is created inside the repo, and a directory snapshot
asserts the audit_package directory is untouched.
"""

from __future__ import annotations

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

# Paths are resolved relative to this test file so the differential runs from any checkout
# (the frozen runner and the installed tool are both siblings of the repo root).
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNNER_PATH = _REPO_ROOT / "audit_package" / "triad_origin_b01_b10_audit.py"
TOOL_PATH = _REPO_ROOT / "tools" / "jcs_canonical.py"
FROZEN_RUNNER_SHA256 = "12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2"

# The repo tree must never gain files from this test process (incl. __pycache__).
sys.dont_write_bytecode = True

# Sibling-or-skip: the frozen runner is deliberately untracked (audit_package/ is gitignored),
# so it is absent in a fresh clone / CI checkout and present only when the operator deploys it
# beside the repo. Skip the whole differential module cleanly when it is not present.
if not RUNNER_PATH.is_file():
    pytest.skip(
        "frozen audit runner absent (audit_package/ untracked); jcs_canonical differential runs "
        "only when the runner is deployed beside the repo",
        allow_module_level=True,
    )

_RUNNER_SOURCE = RUNNER_PATH.read_text(encoding="utf-8")
if 'if __name__ == "__main__":' not in _RUNNER_SOURCE:
    raise RuntimeError("frozen runner lacks a __main__ guard; importing it would execute main")
_ACTUAL_SHA = hashlib.sha256(RUNNER_PATH.read_bytes()).hexdigest()
if _ACTUAL_SHA != FROZEN_RUNNER_SHA256:
    raise RuntimeError(
        f"frozen runner SHA-256 mismatch: {_ACTUAL_SHA} != {FROZEN_RUNNER_SHA256}; "
        "differential results would not be anchored to the frozen law"
    )

_AUDIT_DIR_BEFORE = sorted(p.name for p in RUNNER_PATH.parent.iterdir())


def _load(name: str, path: pathlib.Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The runner's frozen dataclasses resolve annotations via sys.modules[__module__],
    # so the module must be registered before exec (standard importlib recipe).
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _load("frozen_audit_runner", RUNNER_PATH)
tool = _load("staged_jcs_canonical", TOOL_PATH)

_AUDIT_DIR_AFTER = sorted(p.name for p in RUNNER_PATH.parent.iterdir())

INT_MAX = 2**53 - 1  # learned bound; test_int_boundary_learned_from_runner proves it below

# RFC 8785 section 3.2.3 key-sorting example (no floats involved).
RFC_SORT_EXAMPLE: dict[str, str] = {
    "€": "Euro Sign",
    "\r": "Carriage Return",
    "דּ": "Hebrew Letter Dalet With Dagesh",
    "1": "One",
    "\U0001f600": "Emoji: Grinning Face",
    "": "Control",
    "ö": "Latin Small Letter O With Diaeresis",
}
RFC_SORT_EXPECTED_ORDER = ["\r", "1", "", "ö", "€", "\U0001f600", "דּ"]


def _deep_list(depth: int) -> Any:
    value: Any = "bottom"
    for _ in range(depth):
        value = [value]
    return value


def _deep_dict(depth: int) -> Any:
    value: Any = None
    for level in range(depth):
        value = {f"k{level}": value, "é": level % 2 == 0}
    return value


BATTERY: list[Any] = [
    None,                                                       # v00
    True,                                                       # v01
    False,                                                      # v02
    0,                                                          # v03
    1,                                                          # v04
    -1,                                                         # v05
    INT_MAX,                                                    # v06
    -INT_MAX,                                                   # v07
    "",                                                         # v08
    "hello",                                                    # v09
    'quote " backslash \\ slash /',                             # v10
    "\x00\x01\x02\x1f",                                         # v11
    "\b\t\n\f\r",                                               # v12
    "é",                                                   # v13
    "日本語テスト",                     # v14
    "\U00010000",                                               # v15
    "\U0001f600 mixed é z",                                # v16
    "   line separators",                             # v17
    " c1 controls",                                 # v18
    [],                                                         # v19
    [None, True, False],                                        # v20
    [1, "two", [3, [4, []]]],                                   # v21
    [True, 1, False, 0],                                        # v22
    {},                                                         # v23
    {"a": 1},                                                   # v24
    {"z": 1, "é": 2, "a": 3},                              # v25 BMP order trap: z < e-acute
    {"｡": "halfwidth", "\U00010000": "astral"},            # v26 UTF-16 vs codepoint
    RFC_SORT_EXAMPLE,                                           # v27
    {"": "empty key", " ": "space", "\t": "tab"},               # v28
    {"a\x00b": 1, "a\x01b": 2},                                 # v29
    {"k": [{"a": [INT_MAX, -INT_MAX, 0]}]},                     # v30
    {"nested": {"deep": {"final": None, "list": [{"x": "y"}]}}},  # v31
    _deep_list(64),                                             # v32
    _deep_dict(32),                                             # v33
    list(range(-10, 11)),                                       # v34
    {"mixed": [{"\U00010348": "gothic"}, "\U00010348", {"a": [None]}]},  # v35
]


def _cli(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        cwd=cwd,
        capture_output=True,
        env=dict(os.environ),
        timeout=60,
    )


def _assert_same_valueerror(value: Any) -> str:
    with pytest.raises(ValueError) as tool_exc:
        tool.jcs_canonical_bytes(value)
    with pytest.raises(ValueError) as runner_exc:
        runner.jcs_canonical_bytes(value)
    assert str(tool_exc.value) == str(runner_exc.value)
    return str(tool_exc.value)


# ---------------------------------------------------------------- frozen anchor


def test_frozen_runner_identity_and_guard() -> None:
    assert hashlib.sha256(RUNNER_PATH.read_bytes()).hexdigest() == FROZEN_RUNNER_SHA256
    assert 'if __name__ == "__main__":' in _RUNNER_SOURCE
    assert runner.TOOL_VERSION == "1.2.0"


def test_repo_audit_package_dir_untouched_by_import() -> None:
    assert _AUDIT_DIR_BEFORE == _AUDIT_DIR_AFTER
    assert "__pycache__" not in _AUDIT_DIR_AFTER
    assert not (RUNNER_PATH.parent / "__pycache__").exists()


def test_tool_imports_only_stdlib() -> None:
    import ast

    tree = ast.parse(TOOL_PATH.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import found: the tool must be self-contained"
            assert node.module is not None
            roots.add(node.module.split(".")[0])
    non_stdlib = roots - set(sys.stdlib_module_names)
    assert not non_stdlib, f"non-stdlib imports in tool: {sorted(non_stdlib)}"


# ------------------------------------------------------------ differential core


@pytest.mark.parametrize(
    "value", BATTERY, ids=[f"v{index:02d}" for index in range(len(BATTERY))]
)
def test_differential_battery_byte_equality(value: Any) -> None:
    expected = runner.jcs_canonical_bytes(value)
    assert tool.jcs_canonical_bytes(value) == expected
    assert isinstance(expected, bytes)


def test_battery_is_large_enough() -> None:
    assert len(BATTERY) >= 30


def test_key_order_permutations_of_same_dict_agree() -> None:
    items = [("z", 1), ("é", 2), ("a", 3), ("\U00010000", 4), ("｡", 5)]
    d_forward = dict(items)
    d_reverse = dict(reversed(items))
    d_rotated = dict(items[2:] + items[:2])
    expected = runner.jcs_canonical_bytes(d_forward)
    assert runner.jcs_canonical_bytes(d_reverse) == expected
    assert tool.jcs_canonical_bytes(d_forward) == expected
    assert tool.jcs_canonical_bytes(d_reverse) == expected
    assert tool.jcs_canonical_bytes(d_rotated) == expected


def test_utf16_code_unit_ordering_differs_from_code_point_ordering() -> None:
    # U+FF61 < U+10000 by code point, but U+10000 encodes to the UTF-16 surrogate
    # pair D800 DC00, and 0xD800 < 0xFF61 -- so the astral key must sort FIRST.
    value = {"｡": 1, "\U00010000": 2}
    out = tool.jcs_canonical_bytes(value)
    assert out == runner.jcs_canonical_bytes(value)
    astral_pos = out.find("\U00010000".encode("utf-8"))
    halfwidth_pos = out.find("｡".encode("utf-8"))
    assert astral_pos != -1 and halfwidth_pos != -1
    assert astral_pos < halfwidth_pos, "keys must sort by UTF-16 code units, not code points"
    # Sanity: code-point ordering would have chosen the opposite order.
    assert sorted(value) == ["｡", "\U00010000"]


def test_rfc8785_section_3_2_3_sorting_example() -> None:
    out = tool.jcs_canonical_bytes(RFC_SORT_EXAMPLE)
    assert out == runner.jcs_canonical_bytes(RFC_SORT_EXAMPLE)
    parsed = json.loads(out.decode("utf-8"))
    assert list(parsed.keys()) == RFC_SORT_EXPECTED_ORDER
    assert parsed == RFC_SORT_EXAMPLE


def test_rfc8785_appendix_vector_structural_rows() -> None:
    # RFC 8785 sample input, with the float-bearing "numbers" row skipped
    # (the receipt domain forbids floats).  The decoded "string" row is:
    # EURO $ U+000F LF A ' B " \ \ " /
    decoded = "€$\nA'B\"\\\\\"/"
    value = {"string": decoded, "literals": [None, True, False]}
    expected = (
        '{"literals":[null,true,false],"string":"'
        "€$"
        "\\u000f"
        "\\n"
        "A'B"
        '\\"'
        "\\\\"
        "\\\\"
        '\\"'
        '/"}'
    ).encode("utf-8")
    assert tool.jcs_canonical_bytes(value) == expected
    assert runner.jcs_canonical_bytes(value) == expected


# ------------------------------------------------------------- error behaviors


@pytest.mark.parametrize(
    "value",
    [
        1.5,
        -0.0,
        float("nan"),
        float("inf"),
        float("-inf"),
        [1.5],
        [0, [None, [2.0]]],
        {"a": [0.0]},
        {"a": {"b": 3.14}},
    ],
    ids=[
        "plain",
        "neg-zero",
        "nan",
        "inf",
        "neg-inf",
        "in-list",
        "nested-list",
        "in-dict-list",
        "nested-dict",
    ],
)
def test_float_rejection_matches_runner(value: Any) -> None:
    message = _assert_same_valueerror(value)
    assert message == "receipt JCS domain prohibits floating-point numbers"


def test_int_boundary_learned_from_runner() -> None:
    # Learn the exact boundary from the frozen runner FIRST.
    assert runner.jcs_canonical_bytes(2**53 - 1) == str(2**53 - 1).encode("utf-8")
    assert runner.jcs_canonical_bytes(-(2**53 - 1)) == str(-(2**53 - 1)).encode("utf-8")
    with pytest.raises(ValueError):
        runner.jcs_canonical_bytes(2**53)
    with pytest.raises(ValueError):
        runner.jcs_canonical_bytes(-(2**53))
    # The tool must match on both sides of the boundary, byte-for-byte.
    assert tool.jcs_canonical_bytes(2**53 - 1) == runner.jcs_canonical_bytes(2**53 - 1)
    assert tool.jcs_canonical_bytes(-(2**53 - 1)) == runner.jcs_canonical_bytes(-(2**53 - 1))
    for out_of_range in (2**53, -(2**53), 2**63, -(2**64)):
        message = _assert_same_valueerror(out_of_range)
        assert message == "receipt JCS integer exceeds exact I-JSON range"
    message = _assert_same_valueerror([{"k": [2**53]}])
    assert message == "receipt JCS integer exceeds exact I-JSON range"


@pytest.mark.parametrize(
    "value",
    [(), (1, 2), {"a"}, b"bytes", bytearray(b"x"), complex(1, 2), frozenset(), object()],
    ids=["empty-tuple", "tuple", "set", "bytes", "bytearray", "complex", "frozenset", "object"],
)
def test_non_json_type_rejection_matches_runner(value: Any) -> None:
    message = _assert_same_valueerror(value)
    assert message == f"receipt JCS domain rejects {type(value).__name__}"


def test_non_string_dict_key_rejection_matches_runner() -> None:
    message = _assert_same_valueerror({1: "x"})
    assert message == "receipt JCS object keys must be strings"
    message = _assert_same_valueerror({"ok": 1, ("t",): 2})
    assert message == "receipt JCS object keys must be strings"


def test_lone_surrogate_string_rejection_matches_runner() -> None:
    message = _assert_same_valueerror("\ud800")
    assert message == "receipt JCS string contains an invalid surrogate"
    message = _assert_same_valueerror(["ok", "\udfff"])
    assert message == "receipt JCS string contains an invalid surrogate"


def test_lone_surrogate_key_rejection_matches_runner() -> None:
    message = _assert_same_valueerror({"\udfff": 1})
    assert message == "receipt JCS key contains an invalid surrogate"


# -------------------------------------------------------- strict_json_loads


def test_strict_json_loads_differential_on_valid_text() -> None:
    text = '{"b": 2, "a": [true, null, {"k": "\\u00e9"}], "n": 9007199254740991}'
    tool_value = tool.strict_json_loads(text)
    runner_value = runner.strict_json_loads(text)
    assert tool_value == runner_value
    assert tool.jcs_canonical_bytes(tool_value) == runner.jcs_canonical_bytes(runner_value)


def test_strict_json_loads_duplicate_key_rejection_matches_runner() -> None:
    text = '{"a": 1, "a": 2}'
    with pytest.raises(tool.DuplicateJSONKey) as tool_exc:
        tool.strict_json_loads(text)
    with pytest.raises(runner.DuplicateJSONKey) as runner_exc:
        runner.strict_json_loads(text)
    assert str(tool_exc.value) == str(runner_exc.value)
    assert type(tool_exc.value).__name__ == type(runner_exc.value).__name__ == "DuplicateJSONKey"
    assert isinstance(tool_exc.value, ValueError)
    with pytest.raises(tool.DuplicateJSONKey):
        tool.strict_json_loads('{"outer": {"x": 1, "x": 2}}')


@pytest.mark.parametrize("text", ["NaN", "Infinity", "-Infinity", "[1, NaN]", '{"a": Infinity}'])
def test_strict_json_loads_non_finite_rejection_matches_runner(text: str) -> None:
    with pytest.raises(json.JSONDecodeError) as tool_exc:
        tool.strict_json_loads(text)
    with pytest.raises(json.JSONDecodeError) as runner_exc:
        runner.strict_json_loads(text)
    assert str(tool_exc.value) == str(runner_exc.value)
    assert "non-finite JSON number" in str(tool_exc.value)


# ------------------------------------------------------------------------ CLI


def test_cli_round_trip_matches_runner(tmp_path: pathlib.Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture_text = (
        '{\n  "z" : 1,\n  "\\u00e9": 2,\n  "a": [true, null, {"k": "v", "n": 9007199254740991}],\n'
        '  "\\uff61": "halfwidth",\n  "astral": "\\ud800\\udc00"\n}\n'
    )
    fixture.write_text(fixture_text, encoding="utf-8")
    value = runner.strict_json_loads(fixture_text)
    expected = runner.jcs_canonical_bytes(value)
    result = _cli([str(fixture)], tmp_path)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert result.stdout == expected


def test_cli_output_is_binary_safe_raw_utf8(tmp_path: pathlib.Path) -> None:
    fixture = tmp_path / "unicode.json"
    fixture.write_text('{"\\u00e9": "\\u20ac"}', encoding="utf-8")
    result = _cli([str(fixture)], tmp_path)
    assert result.returncode == 0
    assert result.stdout == '{"é":"€"}'.encode("utf-8")
    assert result.stdout == runner.jcs_canonical_bytes({"é": "€"})


def test_cli_rfc_appendix_structural_fixture(tmp_path: pathlib.Path) -> None:
    fixture = tmp_path / "rfc.json"
    fixture_text = (
        "{\n"
        '  "string": "\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"\\/",\n'
        '  "literals": [null, true, false]\n'
        "}"
    )
    fixture.write_text(fixture_text, encoding="utf-8")
    decoded = "€$\nA'B\"\\\\\"/"
    parsed = tool.strict_json_loads(fixture_text)
    assert parsed == {"string": decoded, "literals": [None, True, False]}
    result = _cli([str(fixture)], tmp_path)
    assert result.returncode == 0
    assert result.stdout == runner.jcs_canonical_bytes(parsed)


def test_cli_duplicate_key_rejected(tmp_path: pathlib.Path) -> None:
    fixture = tmp_path / "dup.json"
    fixture.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    result = _cli([str(fixture)], tmp_path)
    assert result.returncode == 1
    assert result.stdout == b""
    assert "duplicate JSON object key" in result.stderr.decode("utf-8")


@pytest.mark.parametrize(
    ("text", "stderr_needle"),
    [
        ("1.5", "floating-point"),
        ('{"a": [4.50]}', "floating-point"),
        ("NaN", "non-finite JSON number"),
        ("Infinity", "non-finite JSON number"),
        (str(2**53), "exact I-JSON range"),
        ("{not json", "Expecting"),
    ],
    ids=["float", "nested-float", "nan", "infinity", "big-int", "malformed"],
)
def test_cli_rejections(tmp_path: pathlib.Path, text: str, stderr_needle: str) -> None:
    fixture = tmp_path / "bad.json"
    fixture.write_text(text, encoding="utf-8")
    result = _cli([str(fixture)], tmp_path)
    assert result.returncode == 1
    assert result.stdout == b""
    assert stderr_needle in result.stderr.decode("utf-8")


def test_cli_boundary_int_accepted(tmp_path: pathlib.Path) -> None:
    fixture = tmp_path / "max.json"
    fixture.write_text(str(2**53 - 1), encoding="utf-8")
    result = _cli([str(fixture)], tmp_path)
    assert result.returncode == 0
    assert result.stdout == str(2**53 - 1).encode("utf-8")


def test_cli_missing_operand_and_missing_file(tmp_path: pathlib.Path) -> None:
    result = _cli([], tmp_path)
    assert result.returncode == 1
    assert b"usage:" in result.stderr
    result = _cli([str(tmp_path / "does-not-exist.json")], tmp_path)
    assert result.returncode == 1
    assert result.stderr != b""
    result = _cli(["a.json", "b.json"], tmp_path)
    assert result.returncode == 1
    assert b"usage:" in result.stderr


def test_cli_invalid_utf8_input_rejected(tmp_path: pathlib.Path) -> None:
    fixture = tmp_path / "bad-utf8.json"
    fixture.write_bytes(b'{"a": "\xff\xfe"}')
    result = _cli([str(fixture)], tmp_path)
    assert result.returncode == 1
    assert result.stderr != b""


def test_cli_execution_writes_nothing_next_to_tool(tmp_path: pathlib.Path) -> None:
    # Simulates the fresh-clone tree-mutation law: top-level script execution
    # (WITHOUT PYTHONDONTWRITEBYTECODE) must not create __pycache__ or any other
    # entry beside the tool, because it imports only stdlib.
    tool_dir = TOOL_PATH.parent
    # Recursive snapshot: other deliverable groups share the staging tree, so we
    # assert OUR run adds nothing, not that the tree started pristine.
    before = sorted(str(p.relative_to(tool_dir)) for p in tool_dir.rglob("*"))
    fixture = tmp_path / "ok.json"
    fixture.write_text('{"a": 1}', encoding="utf-8")
    env = dict(os.environ)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    result = subprocess.run(
        [sys.executable, str(TOOL_PATH), str(fixture)],
        cwd=tmp_path,
        capture_output=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0
    assert result.stdout == b'{"a":1}'
    after = sorted(str(p.relative_to(tool_dir)) for p in tool_dir.rglob("*"))
    added = sorted(set(after) - set(before))
    assert added == [], f"CLI execution created files beside the tool: {added}"
    # The specific mutation the tree-mutation law forbids: bytecode for the tool.
    assert not list(tool_dir.rglob("jcs_canonical*.pyc"))
    # And nothing appeared in the working directory either (beside the fixture).
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ok.json"]
