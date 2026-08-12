#!/usr/bin/env python3
"""Build a deterministic read-only E00--E10 scorecard from supplied evidence.

The tool performs no discovery and makes no service calls.  It accepts one closed JSON evidence
document, emits a content-addressed JSON report, and can render the same report as self-contained
HTML.  A withheld report is still emitted so evidence defects remain inspectable.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.canonical import canonical_json  # noqa: E402
from triad_origin.scorecard import (  # noqa: E402
    build_scorecard_from_dict,
    render_scorecard_html,
)
from triad_origin.scorecard.model import ScorecardError  # noqa: E402


class InputError(ValueError):
    """The input bytes do not carry one unambiguous JSON object."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_input(path: pathlib.Path) -> dict:
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda token: (_raise_constant(token)),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, InputError) as exc:
        raise InputError(f"cannot load {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise InputError("scorecard input root must be an object")
    return document


def _raise_constant(token: str):
    raise InputError(f"non-finite JSON number is forbidden: {token}")


def _write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=pathlib.Path, help="closed scorecard evidence JSON")
    parser.add_argument("--json-output", type=pathlib.Path)
    parser.add_argument("--html-output", type=pathlib.Path)
    parser.add_argument(
        "--diagnostic-only",
        action="store_true",
        help="emit a non-FULL diagnostic with exit 0; default publication is fail-closed",
    )
    args = parser.parse_args(argv)

    try:
        report = build_scorecard_from_dict(load_input(args.input))
        rendered_json = canonical_json(report).decode("utf-8") + "\n"
        if args.json_output is not None:
            _write(args.json_output, rendered_json)
        if args.html_output is not None:
            _write(args.html_output, render_scorecard_html(report))
    except (InputError, ScorecardError) as exc:
        print(f"SCORECARD_INPUT_INVALID: {exc}", file=sys.stderr)
        return 1

    if args.json_output is None:
        sys.stdout.write(rendered_json)
    outcome = report["publication"]["outcome"]
    print(
        f"SCORECARD_{outcome}: {report['content_digest']}; "
        f"{len(report['publication']['blockers'])} blockers; "
        f"{len(report['publication']['status_flags'])} status flags",
        file=sys.stderr,
    )
    if not args.diagnostic_only and outcome != "FULL":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
