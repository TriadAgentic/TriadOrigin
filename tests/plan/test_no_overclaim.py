"""CO-08 acceptance — "zero overclaim strings (CI grep)".

The corpus preimage ledger (`docs/plan/CO-08-PREIMAGE-LEDGER.md`) records all 20 declared
preimages as `UNAVAILABLE`, so CO-08 step 3 is in force: the package claim surfaces must not
assert the package is "independently reproducible" or "post-RC4 effective". This is the machine
guard for that acceptance — the hand-audit table in the ledger §4 is the human record; this test
is the enforcing grep so a NEW overclaim cannot land silently.

Scope note (faithful to CO-08 §4): the bare English words "full"/"complete" are hand-adjudicated
row-by-row in the ledger (a repo-wide grep for them is pure false-positive noise — they occur in
verifier requirements, milestone-scope verbs, and honest deficiency statements). The two
UNAMBIGUOUS marketing phrases — "independently reproducible" and "post-RC4 effective" — are the
machine-checkable overclaims, and this guard covers exactly those.

Legitimate, adjudicated uses that this guard permits:
  * "post-RC4 effective" ON A LINE that also NAMES RC5 (RC5_EFFECTIVE_CONSOLIDATION genuinely IS
    the post-RC4 effective consolidation — a true naming, not a package possession-claim), OR that
    NEGATES the claim ("neither … is the post-RC4 effective law", "never effective");
  * "independently reproducible": no legitimate possession-claim use exists while preimages are
    UNAVAILABLE — it must be ABSENT from every editable claim surface.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Editable claim surfaces (READMEs + plan docs). Excluded by design:
#   - docs/spec*/  : frozen historical bytes, hash-pinned in SOURCE_HASHES (not editable claims).
#   - docs/plan/CO-08-PREIMAGE-LEDGER.md : the ledger that ADJUDICATES these phrases (discusses them).
#   - *.py / *.json : code/data, not marketing claim surfaces (the RC5 compiler docstring names itself).
_LEDGER = "docs/plan/CO-08-PREIMAGE-LEDGER.md"


def _claim_surfaces() -> list[pathlib.Path]:
    surfaces: list[pathlib.Path] = []
    for rel in ("README.md", "docs/control/README.md", "docs/governance/README.md",
                "docs/SPEC_INDEX.md"):
        p = ROOT / rel
        if p.is_file():
            surfaces.append(p)
    for p in sorted((ROOT / "docs" / "plan").glob("*.md")):
        if p.relative_to(ROOT).as_posix() != _LEDGER:
            surfaces.append(p)
    return surfaces


_RC5_NAMING = re.compile(r"rc5|neither|never", re.IGNORECASE)


def test_no_independently_reproducible_claim_on_any_claim_surface() -> None:
    offenders: list[str] = []
    for surface in _claim_surfaces():
        for n, line in enumerate(surface.read_text(encoding="utf-8").splitlines(), 1):
            if "independently reproducible" in line.lower():
                offenders.append(f"{surface.relative_to(ROOT)}:{n}: {line.strip()[:100]}")
    assert not offenders, "overclaim 'independently reproducible' on a claim surface:\n" + "\n".join(offenders)


def test_post_rc4_effective_only_names_rc5_or_negates() -> None:
    offenders: list[str] = []
    for surface in _claim_surfaces():
        lines = surface.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "post-rc4 effective" not in line.lower():
                continue
            # A wrapped blockquote can put the "neither …"/RC5 marker on the previous line
            # (or spill onto the next), so search a ±1-line window for the legitimizing marker.
            window = " ".join(lines[max(0, i - 1):i + 2])
            if not _RC5_NAMING.search(window):
                offenders.append(f"{surface.relative_to(ROOT)}:{i + 1}: {line.strip()[:100]}")
    assert not offenders, (
        "'post-RC4 effective' used as a package possession-claim (not naming RC5, not negating):\n"
        + "\n".join(offenders))


def test_the_guard_actually_scans_the_known_surfaces() -> None:
    # Guard-integrity: the surface set must include the control README (where the adjudicated
    # legitimate uses live) — a guard that scans nothing would vacuously pass.
    rels = {s.relative_to(ROOT).as_posix() for s in _claim_surfaces()}
    assert "docs/control/README.md" in rels
    assert _LEDGER not in rels  # the ledger that discusses the phrases is excluded by design
