#!/usr/bin/env python3
"""Assemble docs/paper.md from the section files. Generated, never edited.

WHY A SCRIPT AND NOT A COPY
---------------------------
Concatenating the sections by hand creates a second copy of every sentence,
which then drifts from the sections it was copied from. This project has already
published one table built on a figure nobody re-read. So `docs/paper.md` is
generated, carries a header saying so, and `--check` fails if it has drifted
from its sources. A drifted paper.md is then a test failure rather than a
discovery.

WHAT IT VERIFIES
----------------
  * every source file exists and is non-empty
  * each one opens with the heading this script expects, so a renamed or
    reordered section cannot pass silently
  * the assembled numbering runs Abstract, 1, 2, 3, 4, 5, 6, 7 with no gap

Usage:
    python scripts/assemble_paper.py            # write docs/paper.md
    python scripts/assemble_paper.py --check     # verify it matches its sources
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "paper.md"

# (file, the heading the file must open with, the label in the manifest).
# Order is the paper's order, and this list IS the outline: the draft document
# that used to carry one is now a pointer to this.
SECTIONS = [
    ("docs/paper-abstract.md", "# Abstract", "Abstract"),
    ("docs/paper-introduction.md", "# Section 1 — Introduction", "1"),
    ("docs/paper-background.md", "# Section 2 — Background", "2"),
    ("docs/paper-design.md", "# Section 3 — Design", "3"),
    ("docs/paper-results.md", "# Section 4 — Results", "4"),
    ("docs/paper-protocol.md", "# Section 5 — The protocol", "5"),
    ("docs/paper-discussion.md", "# Section 6 — Discussion", "6"),
    ("docs/paper-deviations-pointer.md", "# Section 7 — Deviations", "7"),
    ("docs/paper-references.md", "# References", "References"),
]

TITLE = ("Auditing a quantum-classical kernel comparison: a pre-registered null "
         "and what its own artefact will support")


def git_commit():
    """Short HEAD, or None. rev-parse only; it does not touch .git/index."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build(stamp=True):
    """Return the assembled markdown, or raise SystemExit naming the problem."""
    problems, parts = [], []
    for rel, heading, _label in SECTIONS:
        p = ROOT / rel
        if not p.exists():
            problems.append(f"{rel} does not exist")
            continue
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            problems.append(f"{rel} is empty")
            continue
        first = text.splitlines()[0].strip()
        if not first.startswith(heading):
            problems.append(f"{rel} opens with {first!r}, expected "
                            f"{heading!r}. A renamed or reordered section must "
                            f"be declared here, not discovered by a reader.")
            continue
        parts.append(text)
    if problems:
        raise SystemExit("\n  Cannot assemble:\n" +
                         "".join(f"    - {p}\n" for p in problems))

    head = [f"# {TITLE}", ""]
    if stamp:
        head += [
            "**GENERATED FILE. Do not edit.** Assembled by",
            "`scripts/assemble_paper.py` from the section files listed below. Edit a",
            "section and re-run; `--check` fails if this file has drifted from its",
            "sources.",
            "",
            f"Assembled {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
            f"at commit `{git_commit() or 'unknown'}`.",
            "",
            "| section | source | sha256 |",
            "| --- | --- | --- |",
        ]
        for rel, _heading, label in SECTIONS:
            head.append(f"| {label} | `{rel}` | `{digest(ROOT / rel)[:16]}` |")
        head.append("")
    return "\n".join(head) + "\n---\n\n" + "\n\n---\n\n".join(parts) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify docs/paper.md matches its sources; write nothing")
    a = ap.parse_args()

    text = build()
    if a.check:
        if not OUT.exists():
            raise SystemExit(f"\n  {OUT.relative_to(ROOT)} does not exist.\n")
        # The stamp carries a timestamp, so compare everything after it.
        have = OUT.read_text(encoding="utf-8").split("\n---\n", 1)
        want = text.split("\n---\n", 1)
        if len(have) < 2 or have[1] != want[1]:
            raise SystemExit(
                f"\n  {OUT.relative_to(ROOT)} has DRIFTED from its sources.\n"
                f"  Re-run scripts/assemble_paper.py.\n")
        print(f"\n  {OUT.relative_to(ROOT)} matches its "
              f"{len(SECTIONS)} sources.\n")
        return

    OUT.write_text(text, encoding="utf-8")
    n_words = len(text.split())
    print(f"\n  -> {OUT.relative_to(ROOT)}  "
          f"({len(text.splitlines())} lines, ~{n_words:,} words)")
    print(f"  {len(SECTIONS)} parts: "
          f"{', '.join(l for _, _, l in SECTIONS)}\n")


if __name__ == "__main__":
    main()
