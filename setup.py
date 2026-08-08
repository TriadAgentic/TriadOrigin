"""Build hook that packages the byte-pinned contract bundle with ``triad_origin``.

The repository keeps one authoritative contract tree at ``contracts/``. A normal wheel must carry
that same tree; editable installs continue to read the repository copy.
"""

from __future__ import annotations

import copy
import gzip
import io
import os
import pathlib
import shutil
import tarfile

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

ROOT = pathlib.Path(__file__).resolve().parent


class BuildPyWithContracts(build_py):
    def run(self) -> None:
        super().run()
        target = pathlib.Path(self.build_lib) / "triad_origin" / "_contracts"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ROOT / "contracts", target)


class DeterministicSdist(sdist):
    """Normalize tar and gzip metadata so identical source bytes yield identical archives."""

    def run(self) -> None:
        super().run()
        for archive in self.archive_files:
            _normalize_sdist(pathlib.Path(archive))


def _normalize_sdist(path: pathlib.Path) -> None:
    try:
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    except ValueError as exc:
        raise RuntimeError("SOURCE_DATE_EPOCH must be a non-negative integer") from exc
    if epoch < 0:
        raise RuntimeError("SOURCE_DATE_EPOCH must be a non-negative integer")

    entries: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(path, mode="r:gz") as source:
        for member in source.getmembers():
            data = source.extractfile(member).read() if member.isfile() else None
            entries.append((copy.copy(member), data))

    temporary = path.with_name(path.name + ".normalized")
    with open(temporary, "wb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=epoch
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target:
                for member, data in sorted(entries, key=lambda entry: entry[0].name):
                    member.uid = 0
                    member.gid = 0
                    member.uname = ""
                    member.gname = ""
                    member.mtime = epoch
                    member.pax_headers = {}
                    if member.isdir():
                        member.mode = 0o755
                    elif member.isfile():
                        member.mode = 0o755 if member.mode & 0o111 else 0o644
                    target.addfile(member, io.BytesIO(data) if data is not None else None)
    temporary.replace(path)


setup(cmdclass={"build_py": BuildPyWithContracts, "sdist": DeterministicSdist})
