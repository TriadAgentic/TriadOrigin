#!/usr/bin/env python3
"""Build or verify a byte-resolving, closed-membership B00R evidence manifest.

The governance library validates every declared entry.  This tool adds the repository-level law
that the library cannot infer from a document alone: when ``--closed-root`` is supplied, the
manifest must name *every* regular file below that directory except the manifest itself, and no
entry may point outside it.  ``--require-tracked`` additionally requires the manifest and every
preimage to be present in Git's index.  Thus a spec cannot silently omit inconvenient evidence.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from triad_origin import governance  # noqa: E402
try:  # importable both as ``python tools/...`` and as ``from tools import ...``
    from tools.b00r_clean_runner import ALLOWED_EMPTY_PATHS  # type: ignore  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from b00r_clean_runner import ALLOWED_EMPTY_PATHS  # type: ignore  # noqa: E402


class ManifestClosureError(ValueError):
    """The declared manifest is not a closed inventory of its evidence root."""


def _safe_relpath(value: str) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _relative_to_root(path: pathlib.Path, root: pathlib.Path, label: str) -> str:
    # Preserve the lexical path so a symlink component cannot disappear through ``resolve()``
    # before the explicit chain check below.
    absolute = path if path.is_absolute() else pathlib.Path.cwd() / path
    try:
        rel = absolute.absolute().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ManifestClosureError(f"{label}_OUTSIDE_REPOSITORY: {path}") from exc
    if not _safe_relpath(rel):
        raise ManifestClosureError(f"{label}_UNSAFE: {rel!r}")
    return rel


def _reject_symlink_chain(root: pathlib.Path, rel: str) -> None:
    cursor = root
    for part in pathlib.PurePosixPath(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ManifestClosureError(f"EVIDENCE_SYMLINK: {rel}")


def _media_type(rel: str) -> str:
    # Do not use platform-dependent mimetype registries in evidence identity.
    if rel.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


def _git_tracked(root: pathlib.Path, rel: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", rel],
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def validate_closed_membership(
    manifest: dict,
    *,
    root: pathlib.Path,
    manifest_path: pathlib.Path,
    closed_root: pathlib.Path,
    require_tracked: bool,
) -> None:
    """Require exact manifest membership for one closed evidence directory."""
    root = root.resolve()
    manifest_rel = _relative_to_root(manifest_path, root, "MANIFEST_PATH")
    closed_rel = _relative_to_root(closed_root, root, "CLOSED_ROOT")
    if manifest_rel != f"{closed_rel}/evidence_manifest.json":
        raise ManifestClosureError(
            "MANIFEST_PATH_NOT_CANONICAL: require "
            f"{closed_rel}/evidence_manifest.json, found {manifest_rel}"
        )
    _reject_symlink_chain(root, manifest_rel)
    if not closed_root.is_dir():
        raise ManifestClosureError(f"CLOSED_ROOT_NOT_DIRECTORY: {closed_rel}")
    _reject_symlink_chain(root, closed_rel)

    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ManifestClosureError("EVIDENCE_MANIFEST_EMPTY")
    if manifest.get("entry_count") != len(entries):
        raise ManifestClosureError(
            f"ENTRY_COUNT_MISMATCH: {manifest.get('entry_count')!r}!={len(entries)}"
        )

    declared: set[str] = set()
    for entry in entries:
        rel = entry.get("path")
        if not _safe_relpath(rel):
            raise ManifestClosureError(f"EVIDENCE_PATH_UNSAFE: {rel!r}")
        if rel in declared:
            raise ManifestClosureError(f"EVIDENCE_DUPLICATE_PATH: {rel}")
        if not rel.startswith(f"{closed_rel}/"):
            raise ManifestClosureError(f"EVIDENCE_OUTSIDE_CLOSED_ROOT: {rel}")
        if rel == manifest_rel:
            raise ManifestClosureError("EVIDENCE_MANIFEST_SELF_REFERENCE")
        expected_media = _media_type(rel)
        if entry.get("media_type") != expected_media:
            raise ManifestClosureError(
                f"EVIDENCE_MEDIA_TYPE_MISMATCH: {rel}: "
                f"{entry.get('media_type')!r}!={expected_media!r}"
            )
        _reject_symlink_chain(root, rel)
        declared.add(rel)

    actual: set[str] = set()
    for candidate in sorted(closed_root.rglob("*")):
        rel = _relative_to_root(candidate, root, "EVIDENCE_PATH")
        _reject_symlink_chain(root, rel)
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ManifestClosureError(f"EVIDENCE_NOT_REGULAR_FILE: {rel}")
        if rel != manifest_rel:
            actual.add(rel)

    omitted = sorted(actual - declared)
    extra = sorted(declared - actual)
    if omitted or extra:
        raise ManifestClosureError(
            f"EVIDENCE_MEMBERSHIP_NOT_CLOSED: omitted={omitted} extra={extra}"
        )

    if require_tracked:
        tracked_paths = sorted(actual | {manifest_rel})
        untracked = [rel for rel in tracked_paths if not _git_tracked(root, rel)]
        if untracked:
            raise ManifestClosureError(f"EVIDENCE_NOT_GIT_TRACKED: {untracked}")


def _load_json(path: pathlib.Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestClosureError(f"{label}_NOT_READABLE_JSON: {exc}") from exc


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build")
    mode.add_argument("--verify")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out")
    parser.add_argument("--closed-root")
    parser.add_argument("--require-tracked", action="store_true")
    args = parser.parse_args(argv)

    root_input = pathlib.Path(args.root)
    if root_input.is_symlink():
        print(f"FAIL: repository root may not be a symlink: {root_input}", file=sys.stderr)
        return 1
    root = root_input.resolve()
    if not root.is_dir():
        print(f"FAIL: repository root is not a directory: {root}", file=sys.stderr)
        return 1
    closed_root = pathlib.Path(args.closed_root) if args.closed_root else None
    if closed_root is not None and not closed_root.is_absolute():
        closed_root = root / closed_root
    allowed_empty_paths = (
        ALLOWED_EMPTY_PATHS
        if closed_root == root / "evidence" / "B00R_G2"
        else frozenset()
    )

    try:
        if args.build:
            spec_path = pathlib.Path(args.build)
            if not spec_path.is_absolute():
                spec_path = root / spec_path
            spec = _load_json(spec_path, "SPEC")
            entries = spec["entries"] if isinstance(spec, dict) else spec
            manifest = governance.build_evidence_manifest(root, entries)
            # Resolve sizes/digests/zero-byte law before writing anything.
            governance.validate_evidence_manifest(
                manifest, root, allowed_empty_paths=allowed_empty_paths)
            text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            if closed_root is not None:
                if not args.out:
                    raise ManifestClosureError("--closed-root build requires --out")
                # Validate against a temporary logical manifest path.  The output itself is the
                # one deliberately excluded member and therefore need not exist yet.
                validate_closed_membership(
                    manifest,
                    root=root,
                    manifest_path=(
                        pathlib.Path(args.out)
                        if pathlib.Path(args.out).is_absolute()
                        else root / args.out
                    ),
                    closed_root=closed_root,
                    require_tracked=False,
                )
            if args.out:
                out_path = pathlib.Path(args.out)
                if not out_path.is_absolute():
                    out_path = root / out_path
                if out_path.is_symlink():
                    raise ManifestClosureError(f"MANIFEST_OUTPUT_SYMLINK: {out_path}")
                out_path.write_text(text, encoding="utf-8")
                print(f"OK: wrote {args.out} ({manifest['entry_count']} entries)")
            else:
                sys.stdout.write(text)
            return 0

        manifest_path = pathlib.Path(args.verify)
        if not manifest_path.is_absolute():
            manifest_path = root / manifest_path
        manifest = _load_json(manifest_path, "MANIFEST")
        governance.validate_evidence_manifest(
            manifest, root, allowed_empty_paths=allowed_empty_paths)
        if closed_root is not None:
            validate_closed_membership(
                manifest,
                root=root,
                manifest_path=manifest_path,
                closed_root=closed_root,
                require_tracked=args.require_tracked,
            )
        elif args.require_tracked:
            raise ManifestClosureError("--require-tracked requires --closed-root")
        print(f"OK: evidence manifest verified ({manifest.get('entry_count')} entries)")
        return 0
    except (KeyError, TypeError, OSError, governance.GovernanceError, ManifestClosureError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
