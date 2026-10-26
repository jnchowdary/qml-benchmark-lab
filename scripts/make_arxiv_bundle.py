#!/usr/bin/env python3
"""Build the arXiv submission from arxiv/, taking only what paper.tex needs.

WHY THIS EXISTS
---------------
On 26 October 2026 the bundle directory held ten files and the submission needs
four. The obvious move is to archive the directory, and it is wrong: that sweeps
in `paper.pdf` alongside its own source, which arXiv handles badly rather than
ignoring, plus `header.tex`, `paper_source.md` and three build artefacts.

`header.tex` is the subtle one. Pandoc's `-H` inlines its contents into the
preamble, so `paper.tex` never references it, yet it sits there looking like
part of the document.

WHY THE LIST IS DERIVED AND NOT WRITTEN DOWN
--------------------------------------------
The first plan was a line in the README naming the four files. That plan is
refuted by this project's own week: a true sentence in README.md went stale
within a day of being written, because nothing executes a document and nobody
re-reads one when the thing it describes moves. A list of four filenames would
rot the first time a figure is added or renamed.

So nothing here declares the contents. They are read out of `paper.tex`, which
is the artefact being submitted, and then cross-checked against the `figures`
the generator recorded in docs/latex-manifest.json. **If those two disagree the
bundle is not written**, because a mismatch means the tex and the manifest
describe different documents and which one is wrong is not for this script to
decide.

WHAT IT REFUSES TO DO
---------------------
  * include a file paper.tex does not reference
  * include any .tex except paper.tex, since a second one invites arXiv to
    pick the wrong main file
  * write a bundle when a referenced file is missing from arxiv/
  * write a bundle when the figures in the tex and in the manifest differ
  * include a path with a directory component, which would unpack a
    subdirectory where arXiv expects files at the root

Usage:
    python3 scripts/make_arxiv_bundle.py
    python3 scripts/make_arxiv_bundle.py --out ~/arxiv-submission.tar.gz
    python3 scripts/make_arxiv_bundle.py --list      # say what would go, write nothing
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "arxiv"
MAIN = "paper.tex"
MANIFEST = ROOT / "docs" / "latex-manifest.json"

GRAPHICS = re.compile(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}")
INPUTS = re.compile(r"\\(?:input|include)\{([^}]+)\}")


def required_files(tex_text):
    """What the submission needs, read out of the document itself.

    Returns (ordered list, problems). The main file first, because arXiv picks
    the main file by looking for \\documentclass and order makes that visible
    to a human reading the archive listing.
    """
    problems = []
    if "\\documentclass" not in tex_text:
        problems.append(f"{MAIN} has no \\documentclass, so it is not a main file")

    figures, seen = [], set()
    for m in GRAPHICS.finditer(tex_text):
        f = m.group(1).strip()
        if f not in seen:
            seen.add(f)
            figures.append(f)

    inputs = sorted({m.group(1).strip() for m in INPUTS.finditer(tex_text)})

    for f in figures + inputs:
        if "/" in f or f.startswith(".."):
            problems.append(f"{f} has a directory component; arXiv expects a flat archive")

    return [MAIN] + figures + inputs, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "arxiv-submission.tar.gz"))
    ap.add_argument("--list", action="store_true",
                    help="print what would be included and excluded; write nothing")
    a = ap.parse_args()

    tex = BUNDLE / MAIN
    if not tex.exists():
        raise SystemExit(f"\n  {tex.relative_to(ROOT)} does not exist. "
                         f"Run scripts/paper_to_latex.py.\n")

    wanted, problems = required_files(tex.read_text(encoding="utf-8"))

    for f in wanted:
        if not (BUNDLE / f).exists():
            problems.append(f"{f} is referenced by {MAIN} but is not in arxiv/")

    # Cross-check the figures against what the generator recorded. The tex is
    # authoritative for what is needed; a disagreement means the two describe
    # different documents and is reported rather than resolved here.
    if MANIFEST.exists():
        recorded = set(json.loads(MANIFEST.read_text(encoding="utf-8")).get("figures", []))
        from_tex = {f for f in wanted if f != MAIN and not f.endswith(".tex")}
        if recorded != from_tex:
            problems.append(
                f"figures disagree: {MAIN} references {sorted(from_tex)}, "
                f"docs/latex-manifest.json records {sorted(recorded)}. "
                f"Regenerate with scripts/paper_to_latex.py.")

    extra_tex = sorted(p.name for p in BUNDLE.glob("*.tex") if p.name != MAIN)
    present = sorted(p.name for p in BUNDLE.iterdir() if p.is_file())
    excluded = [f for f in present if f not in wanted]

    print(f"\n  SUBMISSION, read out of arxiv/{MAIN}\n")
    for f in wanted:
        size = (BUNDLE / f).stat().st_size if (BUNDLE / f).exists() else 0
        print(f"    include  {size:>9,}  {f}")
    for f in excluded:
        why = ("build artefact" if f.rsplit(".", 1)[-1] in ("aux", "log", "out", "toc", "fls")
               else "the compiled output; arXiv wants source, not a PDF beside it"
               if f.endswith(".pdf")
               else "inlined into the preamble by pandoc -H; not referenced"
               if f in extra_tex
               else "not referenced by the document")
        print(f"    exclude  {(BUNDLE / f).stat().st_size:>9,}  {f}   ({why})")

    if problems:
        raise SystemExit("\n  REFUSING to build; nothing was written.\n" +
                         "".join(f"    - {p}\n" for p in problems))

    if a.list:
        print(f"\n  --list given, so nothing was written.\n")
        return

    out = Path(a.out).expanduser()
    with tarfile.open(out, "w:gz") as t:
        for f in wanted:
            t.add(BUNDLE / f, arcname=f)      # arcname: flat, no directory

    with tarfile.open(out) as t:
        names = t.getnames()
    assert names == wanted, f"archive contents {names} != {wanted}"

    print(f"\n  -> {out}  ({out.stat().st_size:,} bytes, {len(names)} files, flat)")
    print(f"  Upload this. Extracting it into an empty directory and running")
    print(f"  pdflatex twice is the only check that matters.\n")


if __name__ == "__main__":
    main()
