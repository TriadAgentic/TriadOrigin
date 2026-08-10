#!/usr/bin/env python3
"""Derive and verify the RC1/RC3/RC4 spec/control counts for TriadOrigin.

Executed by the frozen audit runner (``audit_package/triad_origin_b01_b10_audit.py``,
v1.2.0, SHA-256 ``12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2``)
as the mandatory local command ``python tools/verify_spec_control_counts.py --strict``
(runner ``REQUIRED_LOCAL_COMMANDS`` row ``verify_spec_control_counts``, timeout 300 s).

On success this script writes EXACTLY one strict-JSON object to stdout (one line, one
trailing newline) and exits 0::

    {"schema": "triad.origin.spec_control_counts.v1", "rc1_test_count": 408,
     "rc3_effective_verification_count": 1523, "rc4_fixture_count": 125}

Every count is DERIVED from the repository's own spec/control artifacts — never
hardcoded and printed blindly:

* ``rc1_test_count`` — the "Total target tests" KPI parsed from
  ``docs/spec/08_TRIAD_ORIGIN_V7_VERIFICATION_MATRIX_1.0.0_RC1.html`` (fails loudly
  when the KPI is absent or ambiguous).
* ``rc3_effective_verification_count`` — ``len(verifications)`` of the strict-JSON
  ``docs/control/rc3_effective_control_bundle.json`` (duplicate object keys refuse).
* ``rc4_fixture_count`` — ``len(verifications)`` of the strict-JSON
  ``docs/control/rc4_control_bundle.json``.

Under ``--strict`` each derived value is additionally cross-checked against the pinned
runner expectations (the ``EXPECTED_*`` constants below).  On ANY failure the script
writes a single-line JSON error object to stderr, writes NOTHING to stdout, and exits 1.

Determinism / read-only law: stdlib only, no environment reads, no writes of any kind,
no network, repo root resolved from this file's own location (never the working
directory).  Invoked as a top-level script it imports nothing from the repository, so
it can never create ``__pycache__`` inside an audited clone.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

SCHEMA = "triad.origin.spec_control_counts.v1"
ERROR_SCHEMA = "triad.origin.spec_control_counts.error.v1"

# Pinned expectations, cited verbatim from the frozen audit runner v1.2.0
# (audit_package/triad_origin_b01_b10_audit.py, SHA-256
# 12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2):
#   EXPECTED_RC1_TEST_COUNT = 408                                     (runner line 121)
#   EXPECTED_EFFECTIVE_COUNTS["effective_verification_count"] = 1523  (runner lines 110-120)
#   EXPECTED_RC4_FIXTURE_COUNT = 125                                  (runner line 122)
EXPECTED_RC1_TEST_COUNT = 408
EXPECTED_RC3_EFFECTIVE_VERIFICATION_COUNT = 1523
EXPECTED_RC4_FIXTURE_COUNT = 125

RC1_MATRIX_HTML = "docs/spec/08_TRIAD_ORIGIN_V7_VERIFICATION_MATRIX_1.0.0_RC1.html"
RC3_EFFECTIVE_BUNDLE = "docs/control/rc3_effective_control_bundle.json"
RC4_CONTROL_BUNDLE = "docs/control/rc4_control_bundle.json"

_RC1_KPI_LABEL = "Total target tests"
# Anchored on the <h3> label; tolerant of attribute and whitespace variance around the
# preceding KPI <div> (the source bytes read
# '<div class="kpi">408</div><h3>Total target tests</h3>').
_RC1_KPI_RE = re.compile(
    r"<div\b[^>]*\bclass\s*=\s*(?P<q>[\"'])(?:[^\"'>]*\s)?kpi(?:\s[^\"'>]*)?(?P=q)[^>]*>"
    r"\s*(?P<value>\d+)\s*</div>\s*"
    r"<h3\b[^>]*>\s*Total\s+target\s+tests\s*</h3>",
    re.IGNORECASE,
)


class CountDerivationError(ValueError):
    """A spec/control count could not be honestly derived."""


class DuplicateJSONKey(ValueError):
    """Mirror of the frozen audit runner's strict-JSON duplicate-key refusal."""


def strict_json_loads(value: str) -> object:
    """Strict JSON: duplicate object keys and non-finite numbers are refusals.

    Behaviour mirrors the frozen runner's ``strict_json_loads`` exactly.
    """

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise DuplicateJSONKey(f"duplicate JSON object key {key!r}")
            result[key] = item
        return result

    def reject_constant(token: str) -> object:
        raise json.JSONDecodeError(f"non-finite JSON number {token}", value, 0)

    return json.loads(
        value, object_pairs_hook=reject_duplicates, parse_constant=reject_constant
    )


def repo_root_from_script() -> pathlib.Path:
    """Repo root = parent of the ``tools/`` directory holding this script (never cwd)."""
    return pathlib.Path(__file__).resolve().parent.parent


def _read_text(path: pathlib.Path, label: str) -> str:
    if not path.is_file():
        raise CountDerivationError(f"{label} missing at {path.as_posix()}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CountDerivationError(f"{label} unreadable at {path.as_posix()}: {exc}") from exc


def derive_rc1_test_count(repo_root: pathlib.Path) -> int:
    """Extract the 'Total target tests' KPI from the RC1 verification matrix HTML."""
    text = _read_text(repo_root / RC1_MATRIX_HTML, "RC1 verification matrix HTML")
    values = [match.group("value") for match in _RC1_KPI_RE.finditer(text)]
    if not values:
        raise CountDerivationError(
            f"RC1 KPI {_RC1_KPI_LABEL!r} absent from {RC1_MATRIX_HTML}"
        )
    if len(values) > 1:
        raise CountDerivationError(
            f"RC1 KPI {_RC1_KPI_LABEL!r} ambiguous in {RC1_MATRIX_HTML}: "
            f"{len(values)} matches {values!r}"
        )
    return int(values[0])


def _verifications_length(repo_root: pathlib.Path, relative: str, label: str) -> int:
    text = _read_text(repo_root / relative, label)
    try:
        data = strict_json_loads(text)
    except (json.JSONDecodeError, DuplicateJSONKey) as exc:
        raise CountDerivationError(f"{label} is not strict JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CountDerivationError(f"{label} root must be a JSON object")
    verifications = data.get("verifications")
    if not isinstance(verifications, list):
        raise CountDerivationError(f"{label} 'verifications' must be a JSON array")
    return len(verifications)


def derive_rc3_effective_verification_count(repo_root: pathlib.Path) -> int:
    """``len(verifications)`` of the strict-JSON RC3 effective control bundle."""
    return _verifications_length(
        repo_root, RC3_EFFECTIVE_BUNDLE, "RC3 effective control bundle"
    )


def derive_rc4_fixture_count(repo_root: pathlib.Path) -> int:
    """``len(verifications)`` of the strict-JSON RC4 control bundle."""
    return _verifications_length(repo_root, RC4_CONTROL_BUNDLE, "RC4 control bundle")


def derive_counts(repo_root: pathlib.Path) -> dict[str, object]:
    """Derive all three counts; key order matches the runner's own self-test payload."""
    return {
        "schema": SCHEMA,
        "rc1_test_count": derive_rc1_test_count(repo_root),
        "rc3_effective_verification_count": derive_rc3_effective_verification_count(
            repo_root
        ),
        "rc4_fixture_count": derive_rc4_fixture_count(repo_root),
    }


def strict_mismatches(counts: dict[str, object]) -> list[str]:
    """Compare derived counts against the pinned runner expectations."""
    expected: dict[str, int] = {
        "rc1_test_count": EXPECTED_RC1_TEST_COUNT,
        "rc3_effective_verification_count": EXPECTED_RC3_EFFECTIVE_VERIFICATION_COUNT,
        "rc4_fixture_count": EXPECTED_RC4_FIXTURE_COUNT,
    }
    return [
        f"{key}={counts.get(key)!r}; expected {wanted}"
        for key, wanted in expected.items()
        if counts.get(key) != wanted
    ]


def _fail(message: str) -> int:
    """Loud single-line JSON error on stderr; NOTHING on stdout; exit code 1."""
    sys.stderr.write(json.dumps({"schema": ERROR_SCHEMA, "error": message}) + "\n")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_spec_control_counts.py",
        description=(
            "Derive the RC1/RC3/RC4 spec/control counts from the repository's own "
            "artifacts and emit exactly one strict-JSON object on stdout."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "additionally cross-check each derived value against the pinned audit-"
            "runner v1.2.0 expectations (408/1523/125); any mismatch exits 1"
        ),
    )
    args = parser.parse_args(argv)
    try:
        counts = derive_counts(repo_root_from_script())
    except CountDerivationError as exc:
        return _fail(str(exc))
    if args.strict:
        mismatches = strict_mismatches(counts)
        if mismatches:
            return _fail("strict pin mismatch: " + "; ".join(mismatches))
    sys.stdout.write(json.dumps(counts) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
