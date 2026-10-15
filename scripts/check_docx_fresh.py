#!/usr/bin/env python3
"""Is each .docx export still current against the markdown it was built from?

WHY THIS EXISTS
---------------
`scripts/report_to_docx.js` was written because weeks 1 to 3 were transcribed
into Word by hand and "a record and its document drift, and the drift is
invisible because nobody diffs a .docx against a .md". That argument was right
and the drift happened anyway. On 15 October 2026 `docs/deviations.docx` was
sixteen days behind a record that had grown from roughly 1,250 lines to 2,665,
so it ended before D14 was adopted and contained nothing about D16. A generator
with no freshness check is a convention, not a guarantee.

WHY A HASH AND NOT A TIMESTAMP
------------------------------
A fresh clone gives every file the checkout time, so mtime comparison reports a
stale export in a clone as current. The manifest stores the SHA-256 of the
source markdown at export time, which survives cloning.

THREE STATES, NOT TWO
---------------------
  CURRENT   the source's hash matches the manifest entry
  STALE     the entry exists and the source has changed since  -> exit 1
  UNRECORDED  the .docx exists with no manifest entry

UNRECORDED is not an error. Weeks 1 to 3 were made by hand before this
generator existed, and asserting that they match their markdown would be a
claim nobody has checked. They are reported as what they are and left alone.
An entry whose .docx is missing is an error, because the manifest then
describes a file that does not exist.

Usage:
    python scripts/check_docx_fresh.py
    python scripts/check_docx_fresh.py --quiet   # print only problems
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "docx-manifest.json"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true",
                    help="print only STALE, MISSING and unreadable entries")
    args = ap.parse_args()

    entries = {}
    if MANIFEST.exists():
        try:
            entries = json.loads(MANIFEST.read_text(encoding="utf-8")).get("exports", {})
        except json.JSONDecodeError as e:
            raise SystemExit(f"\n  {MANIFEST.relative_to(ROOT)} is not valid "
                             f"JSON: {e}\n")

    on_disk = sorted(p for p in (ROOT / "docs").glob("*.docx"))
    rows, stale, missing, unreadable = [], [], [], []

    for p in on_disk:
        rel = str(p.relative_to(ROOT))
        e = entries.get(rel)
        if e is None:
            rows.append((rel, "UNRECORDED", "no manifest entry; provenance "
                                            "not recorded, not assumed"))
            continue
        src = ROOT / e["source"]
        if not src.exists():
            unreadable.append(rel)
            rows.append((rel, "UNREADABLE", f"source {e['source']} is missing"))
            continue
        got = sha256(src)
        if got == e.get("source_sha256"):
            rows.append((rel, "CURRENT", f"matches {e['source']} as of "
                                         f"{e.get('generated_at', '?')}"))
        else:
            stale.append(rel)
            rows.append((rel, "STALE", f"{e['source']} has changed since "
                                       f"{e.get('generated_at', '?')}"))

    for rel in sorted(set(entries) - {str(p.relative_to(ROOT)) for p in on_disk}):
        missing.append(rel)
        rows.append((rel, "MISSING", "in the manifest but not on disk"))

    show = [r for r in rows if r[1] != "CURRENT"] if args.quiet else rows
    if show:
        print()
        for rel, state, detail in show:
            print(f"  [{state:<10}] {rel:<34} {detail}")

    n_cur = sum(1 for r in rows if r[1] == "CURRENT")
    n_unrec = sum(1 for r in rows if r[1] == "UNRECORDED")
    print(f"\n  {len(on_disk)} exports: {n_cur} current, {len(stale)} stale, "
          f"{n_unrec} provenance unrecorded, {len(missing)} missing.\n")

    if stale or missing or unreadable:
        bad = stale + missing + unreadable
        raise SystemExit(
            f"  {len(bad)} export(s) need attention. Regenerate with\n"
            f"    node scripts/report_to_docx.js <source.md> <output.docx>\n")


if __name__ == "__main__":
    main()
