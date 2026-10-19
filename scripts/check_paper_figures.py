#!/usr/bin/env python3
"""Re-derive the paper's load-bearing figures from the stored records.

WHY THIS EXISTS
---------------
Section 5.6 of the paper says, of this project's own protocol:

    Tier 1 reads records and Tier 2 reads kernels. Nothing in this protocol
    reads this project's own analysis and reporting code for claims the data
    does not support.

That sentence is the honest summary of three defects found by inspection rather
than by any check: a superseded exclusion bound printed for eleven days, a Holm
family size printed as a literal, a table headed "all cells" that silently
skipped cells. This script is the first thing in the repository that reads the
paper itself and asks whether a figure it prints is still what the records say.

WHY A DECLARED REGISTRY AND NOT A SEARCH
----------------------------------------
Searching the records for a figure's digits does not work, and it fails in the
direction that matters: it finds matches. On 19 October 2026 a numeric walk over
`results/` was run for four of the paper's figures and every single hit was a
collision between unrelated quantities. The paper's `76.5` is a percentage of
units; the match was a geometric difference of 76.538. Its `0.1712` is a
Spearman rho; the match was a `d_normap`. Its `0.5523` is D16's elasticity; the
match was another g value. Four figures, four false positives, and a search had
no way to tell any of them from provenance.

So every entry below names its source file and its accessor by hand. That is the
same shape as `D6_ARM` and `D6_H1` in `scripts/audit_sweep.py`, and it carries
the same risk: the first version of that script mapped a quantity wrongly and
reported a correct record as not reproducing. Each entry here therefore states
which quantity it holds, in words, next to the accessor that fetches it.

HOW A FIGURE IS COMPARED
------------------------
Not within a tolerance somebody chose. A figure quoted to four decimal places
claims exactly that the underlying value rounds to it, so the check is

    stated == round(derived, decimals in the stated figure)

Fraud's exclusion bound is 0.0062713592 in the records and 0.0063 in the paper,
and that is correct rather than approximate. A tolerance would have hidden the
difference between a figure that still rounds correctly and one that no longer
does.

COVERAGE IS REPORTED, NEVER IMPLIED
-----------------------------------
This project has already shipped a coverage report that flattered itself: the
mutation harness scanned only the files it had mutants for and printed "40
uncovered" where the truth was 340. So this script counts every decimal figure
in the paper as its denominator and says plainly how few are checked. The
uncovered count deliberately includes section cross-references, arXiv numbers
and DOIs that are not measurements at all, because a script that filtered those
by pattern would be guessing, and a guess in the denominator is how the
mutation harness came to overstate itself.

Usage:
    python3 scripts/check_paper_figures.py
    python3 scripts/check_paper_figures.py --quiet    # only problems

Imports json, re, argparse and pathlib. Nothing else, so the figures can be
checked without installing the research environment, for the same reason
scripts/adjudicate_grid.py can.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER_SECTIONS = sorted((ROOT / "docs").glob("paper-*.md"))

# Any decimal number, used only for the coverage denominator. It cannot tell a
# measurement from a section number, and is not asked to.
DECIMAL = re.compile(r"(?<![\w.])[-+]?\d+\.\d+(?:e[-+]?\d+)?(?![\w])", re.I)


def load(rel):
    """A stored record. .jsonl comes back as a list, .json as it was written."""
    p = ROOT / rel
    if not p.exists():
        return None
    if p.suffix == ".jsonl":
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------- accessors
#
# One function per quantity, named for the quantity and not for the figure, so
# that a reader checks the mapping rather than the arithmetic.

def h1_pair_mde(table, dataset, n, arm):
    """D6's H1-pair MDE for one cell: the exclusion-bound quantity.

    NOT the arm-level MDE in the same row. Those are different numbers about
    different comparisons, and conflating them is the error the first version
    of scripts/audit_sweep.py made, which made it report a correct record as
    failing to reproduce. The row carries both; this reads `h1_mde`.
    """
    rows = [r for r in table["rows"]
            if r.get("dataset") == dataset and r.get("n_per_class") == n
            and r.get("arm") == arm]
    if len(rows) != 1:
        raise LookupError(f"{len(rows)} rows match {dataset} n={n} {arm}, expected 1")
    v = rows[0].get("h1_mde")
    if v is None:
        raise LookupError(f"{dataset} n={n} {arm} carries no h1_mde")
    return v


def share_with_no_selected_lambda(units):
    """Percentage of units on which Huang's own g_tra rule selects no lambda.

    D16's headline. `selected_lambda` is null exactly when no lambda in the
    declared grid is admissible; on the stored sweep `admissible` is false on
    the same records, every one of them, so the two readings agree and this
    uses the one the rule is about.
    """
    if not units:
        raise LookupError("no unit records")
    return 100.0 * sum(1 for u in units if u.get("selected_lambda") is None) / len(units)


# ---------------------------------------------------------------- registry
#
# stated   the figure exactly as the paper prints it; its decimal places set
#          the precision the comparison is made at
# quantity what it is, in words, so the accessor can be checked rather than
#          trusted
# source   the stored record it is re-derived from
# derive   how

FIGURES = [
    dict(stated="0.0608",
         quantity="churn primary-cell H1-pair MDE, the registered exclusion bound",
         source="results/audits/d6_table.json",
         derive=lambda d: h1_pair_mde(d, "churn", 250, "registered")),
    dict(stated="0.0063",
         quantity="fraud primary-cell H1-pair MDE, the registered exclusion bound",
         source="results/audits/d6_table.json",
         derive=lambda d: h1_pair_mde(d, "fraud", 250, "registered")),
    # The churn bandwidth-arm H1-pair MDE, 0.0233, was an entry here on the
    # first run and the stale-entry check removed it. D6_H1 in
    # scripts/audit_sweep.py carries that figure, which is why it was added;
    # the paper does not quote it anywhere and does not discuss the bandwidth
    # arm's exclusion bound at all. A record holding a figure is not the paper
    # claiming it, and this registry checks the paper's claims.
    dict(stated="76.5",
         quantity="percentage of units where Huang's g_tra rule selects no lambda",
         source="results/audits/g_units_gtra.jsonl",
         derive=share_with_no_selected_lambda),
]


def decimals(s):
    return len(s.split(".")[1]) if "." in s else 0


def where_quoted(stated):
    """Which paper sections print this figure, discovered rather than declared.

    A declared list of sections would drift from the paper the first time a
    sentence moved. An entry no figure quotes anywhere is a stale entry and is
    reported as a failure, because a registry that checks claims the paper no
    longer makes overstates its own coverage.
    """
    pat = re.compile(rf"(?<![\w.]){re.escape(stated)}(?![\w.])")
    return [p.name.replace("paper-", "").replace(".md", "")
            for p in PAPER_SECTIONS
            if pat.search(p.read_text(encoding="utf-8"))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="print only problems")
    args = ap.parse_args()

    checked, problems = set(), []
    rows = []
    for f in FIGURES:
        stated, src = f["stated"], f["source"]
        secs = where_quoted(stated)
        data = load(src)
        if data is None:
            problems.append(f"{stated}: {src} is not in this checkout")
            rows.append((stated, "NO SOURCE", src, f["quantity"], secs))
            continue
        if not secs:
            problems.append(f"{stated}: quoted in no paper section; the entry is stale")
            rows.append((stated, "STALE ENTRY", "-", f["quantity"], secs))
            continue
        try:
            got = f["derive"](data)
        except LookupError as e:
            problems.append(f"{stated}: cannot derive from {src}: {e}")
            rows.append((stated, "NOT DERIVABLE", str(e)[:44], f["quantity"], secs))
            continue
        rounded = round(got, decimals(stated))
        if abs(rounded - float(stated)) < 1e-12:
            checked.add(stated)
            rows.append((stated, "AGREES", f"{got:.10g}", f["quantity"], secs))
        else:
            problems.append(f"{stated}: the records give {got:.10g}, which rounds to "
                            f"{rounded:g}, and the paper prints {stated}")
            rows.append((stated, "DISAGREES", f"{got:.10g}", f["quantity"], secs))

    if not args.quiet or problems:
        print("\nPAPER FIGURES, RE-DERIVED FROM THE RECORDS\n")
        for stated, state, got, quantity, secs in rows:
            if args.quiet and state == "AGREES":
                continue
            print(f"  [{state:<13}] {stated:<8} <- {got}")
            print(f"                  {quantity}")
            print(f"                  quoted in: {', '.join(secs) or 'nowhere'}")

    # The denominator is every decimal figure the paper prints, uninterpreted.
    seen = set()
    for p in PAPER_SECTIONS:
        seen.update(DECIMAL.findall(p.read_text(encoding="utf-8")))
    print(f"\n  {len(checked)} of {len(seen)} distinct decimal figures in the paper are "
          f"re-derived here.")
    print(f"  The other {len(seen) - len(checked)} are NOT checked. That count includes "
          f"section\n  cross-references, arXiv numbers and DOIs, which are not "
          f"measurements; this\n  script does not try to tell those apart from figures "
          f"it simply has not\n  covered, because a guess in the denominator is how this "
          f"project's mutation\n  harness came to overstate its own coverage.\n")

    if problems:
        raise SystemExit("  " + f"{len(problems)} problem(s):\n" +
                         "".join(f"    - {p}\n" for p in problems))


if __name__ == "__main__":
    main()
