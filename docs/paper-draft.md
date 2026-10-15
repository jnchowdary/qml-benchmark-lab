# Paper draft — superseded, 15 October 2026

**This document no longer holds content.** It was the working draft between
weeks 9 and 12, and every part of it has moved into a section file. It is kept
as a pointer rather than deleted so that anything citing it still lands
somewhere, and reduced to a pointer rather than frozen so that **no second,
drifting copy of the results exists in this repository**.

| what this document held | where it is now |
| --- | --- |
| §1, the framing fork and decision | D15 in `docs/deviations.md`, the authoritative record of it |
| §2, the outline | `scripts/assemble_paper.py`, whose `SECTIONS` list *is* the outline and is checked on every run |
| §3, Results | **`docs/paper-results.md`**, as §4.1 to §4.6 |
| §4, Limitations | **`docs/paper-results.md`**, as §4.7 |
| §5, Figures | §4 of the paper, where the three figures now appear inline. The exclusion decision this document recorded was **reversed**: the PNGs are committed as named exceptions to `.gitignore`, for the reason §4.7 gives |
| §6, what the draft lacked | nothing it listed is still missing. The sections are written, and the two stdout-only families were persisted on 6 October |

**Why the content was moved rather than copied.** From 10 October the paper is
assembled by `scripts/assemble_paper.py` into `docs/paper.md`, and `--check`
fails if that file has drifted from its sources. A draft holding its own copy of
the results sat **outside** that check, so the same figures lived in two
hand-maintained places. This project has already published one table built on a
figure nobody re-read, and two copies of a results section is how that happens
again. The duplicate was created on 10 October, by the same change that added
the assembler, and removed here.

**The original is in git**, at every commit up to and including `3135448`.
Nothing is lost by this file being short.
